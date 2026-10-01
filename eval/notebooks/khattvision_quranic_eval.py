"""KhaṭṭVision v1 on the 567-image Quranic-calligraphy set: the Kaggle notebook converted to run locally.

Source: notebookfc4bcd6109.ipynb (cells copied verbatim). Changes for this machine only:
  - no pip-install cell (the nun venv already pins transformers 5.15.0 + unsloth);
  - HF token from the environment (the notebook's hardcoded token is NOT used);
  - outputs in data/eval_quranic/ (gitignored: the dataset is private) instead of /kaggle/working;
  - display() prints tables.
Run: CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python eval/notebooks/khattvision_quranic_eval.py
"""


def display(obj):
    print((obj.data if hasattr(obj, "data") else obj).to_string())


# ---- notebook cell 3 ----
import os
import re
import gc
import json
import math
import copy
import random
import shutil
import unicodedata
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm.auto import tqdm

SEED = 3407
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

BASE_MODEL = "unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit"
ADAPTER_MODEL = "NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA"
ADAPTER_REVISION = "2cdaa0fd967f1a0ac78d044df8930b410dc2b326"

DATASET_REPO = "Omartificial-Intelligence-Space/Quranic-calligraphy"
DATASET_REVISION = "ea1dbb473aa59990acf21e6841fd62fe6aaf04e1"
SPLIT_FILE = "metadata/reproduced_training_split.csv"

MAX_NEW_TOKENS = 192
MAX_IMAGE_PIXELS = 448 * 448
MAX_IMAGE_SIDE = 896
EVAL_LIMIT = None  # Keep None to evaluate all 567 images.

WORK_DIR = Path("data/eval_quranic")
WORK_DIR.mkdir(parents=True, exist_ok=True)
PREDICTIONS_JSONL = WORK_DIR / "quranic_ocr_predictions.jsonl"

assert torch.cuda.is_available(), "A CUDA GPU is required."
print("PyTorch:", torch.__version__)
print("Visible GPUs:", torch.cuda.device_count())
for i in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(i)
    print(f"GPU {i}: {props.name} — {props.total_memory / 2**30:.1f} GiB")

# ---- notebook cell 4 ----
from huggingface_hub import login

HF_TOKEN = os.environ.get("HF_TOKEN")
assert HF_TOKEN, "Set HF_TOKEN; the evaluation dataset is private."
login(token=HF_TOKEN, add_to_git_credential=False)
print("Hugging Face authentication succeeded.")

# ---- notebook cell 6 ----
from datasets import load_dataset
from huggingface_hub import hf_hub_download

dataset = load_dataset(
    DATASET_REPO,
    split="train",
    revision=DATASET_REVISION,
    token=HF_TOKEN,
)
assert len(dataset) == 567, len(dataset)
assert set(dataset["category"]) == {"quranic"}

split_path = hf_hub_download(
    repo_id=DATASET_REPO,
    repo_type="dataset",
    filename=SPLIT_FILE,
    revision=DATASET_REVISION,
    token=HF_TOKEN,
)
split_df = pd.read_csv(split_path)
split_map = dict(zip(split_df["image_id"].astype(str), split_df["reproduced_original_split"]))
assert len(split_map) == 567

dataset_ids = [str(x) for x in dataset["image_id"]]
assert set(dataset_ids) == set(split_map), "Split metadata and dataset image IDs do not match."

split_counts = pd.Series([split_map[x] for x in dataset_ids]).value_counts()
print("Rows:", len(dataset))
print("Split counts:", split_counts.to_dict())
print("Annotated regions:", sum(len(x) for x in dataset["text"]))
print("Total words:", sum(dataset["total_words"]))

# ---- notebook cell 8 ----
# Unsloth must be imported before Transformers so its patches are applied.
from unsloth import FastModel
import transformers

print("Transformers:", transformers.__version__)
assert transformers.__version__ == "5.15.0", transformers.__version__

# Load the adapter repository directly. Unsloth resolves the base checkpoint,
# keeps the pre-quantized model on the visible GPUs, and attaches the LoRA.
# This avoids Transformers device_map='auto' spilling 4-bit modules to CPU/disk.
model, processor = FastModel.from_pretrained(
    model_name=ADAPTER_MODEL,
    revision=ADAPTER_REVISION,
    max_seq_length=1024,
    load_in_4bit=True,
    use_gradient_checkpointing=False,
    offload_embedding=False,
    token=HF_TOKEN,
)
FastModel.for_inference(model)
model.eval()

# Fail loudly if the repository was resolved as the base model without LoRA.
lora_layers = [name for name, module in model.named_modules() if hasattr(module, "lora_A")]
assert lora_layers, "No LoRA layers were found; the adapter was not loaded."

device_map = getattr(model, "hf_device_map", {}) or {}
offloaded = {
    name: dev for name, dev in device_map.items()
    if str(dev) in {"cpu", "disk"}
}
assert not offloaded, f"Unexpected CPU/disk offload: {offloaded}"

try:
    processor.image_processor.resample = Image.Resampling.BICUBIC
except Exception:
    pass

INPUT_DEVICE = torch.device("cuda:0")
print("Model loaded:", type(model).__name__)
print("Processor loaded:", type(processor).__name__)
print("LoRA layers:", len(lora_layers))
print("Device map:", device_map)
print("Input device:", INPUT_DEVICE)

# ---- notebook cell 10 ----
OCR_INSTRUCTION = (
    "اقرأ جميع النصوص العربية الظاهرة في لوحة الخط. "
    "أعد النص فقط دون شرح، وافصل المقاطع بسطر جديد."
)

ARABIC_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭ]")

def normalize_whitespace(text):
    text = unicodedata.normalize("NFKC", str(text))
    return re.sub(r"\s+", " ", text).strip()

def normalize_arabic(text):
    text = unicodedata.normalize("NFKC", str(text))
    text = ARABIC_DIACRITICS.sub("", text)
    text = re.sub("[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[^؀-ۿ0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def prepare_image_for_model(image):
    image = image.convert("RGB")
    width, height = image.size
    area_scale = math.sqrt(MAX_IMAGE_PIXELS / max(width * height, 1))
    side_scale = MAX_IMAGE_SIDE / max(width, height)
    scale = min(1.0, area_scale, side_scale)
    if scale >= 1.0:
        return image
    new_width = max(28, int((width * scale) // 28) * 28)
    new_height = max(28, int((height * scale) // 28) * 28)
    return image.resize((new_width, new_height), Image.Resampling.BICUBIC)

def build_prompt():
    messages = [{
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "text", "text": OCR_INSTRUCTION},
        ],
    }]
    prompt = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
    )
    # Required by the Muse Glimmer template used during fine-tuning.
    return prompt + " to=user<|message|>"

PROMPT = build_prompt()

@torch.inference_mode()
def predict_ocr(image):
    image = prepare_image_for_model(image)
    inputs = processor(
        text=[PROMPT],
        images=[[image]],
        add_special_tokens=False,
        return_tensors="pt",
    ).to(INPUT_DEVICE)

    generation_config = copy.deepcopy(model.generation_config)
    generation_config.max_length = None
    generation_config.max_new_tokens = MAX_NEW_TOKENS
    generation_config.do_sample = False
    generation_config.use_cache = True

    output_ids = model.generate(**inputs, generation_config=generation_config)
    new_tokens = output_ids[:, inputs["input_ids"].shape[1]:]
    prediction = processor.tokenizer.batch_decode(
        new_tokens,
        skip_special_tokens=True,
    )[0].strip()
    del inputs, output_ids, new_tokens
    return prediction

# ---- notebook cell 12 ----
existing = {}
if PREDICTIONS_JSONL.exists():
    with PREDICTIONS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if not row.get("error"):
                    existing[str(row["image_id"])] = row
print("Already completed:", len(existing))

indices = list(range(len(dataset)))
if EVAL_LIMIT is not None:
    indices = indices[:EVAL_LIMIT]

for idx in tqdm(indices, desc="KhaṭṭVision OCR"):
    sample = dataset[idx]
    image_id = str(sample["image_id"])
    if image_id in existing:
        continue

    reference = "\n".join(sample["text"])
    row = {
        "dataset_index": idx,
        "image_id": image_id,
        "original_split": split_map[image_id],
        "style": sample["style"],
        "category": sample["category"],
        "reference": reference,
        "prediction": None,
        "error": None,
    }
    try:
        row["prediction"] = predict_ocr(sample["image"])
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        if "out of memory" in str(exc).lower():
            torch.cuda.empty_cache()

    with PREDICTIONS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if not row["error"]:
        existing[image_id] = row

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

print("Successful predictions:", len(existing), "/", len(indices))

# ---- notebook cell 14 ----
from jiwer import cer as jiwer_cer, wer as jiwer_wer
from sacrebleu.metrics import CHRF

chrf = CHRF(word_order=2)

records = []
with PREDICTIONS_JSONL.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

# Keep the newest successful record if a failed row was retried.
latest = {}
for row in records:
    image_id = str(row["image_id"])
    if not row.get("error"):
        latest[image_id] = row

pred_df = pd.DataFrame(latest.values()).sort_values("dataset_index").reset_index(drop=True)
assert len(pred_df) == len(indices), (
    f"Only {len(pred_df)} of {len(indices)} images succeeded. "
    "Inspect failed rows before reporting metrics."
)

def nonempty(values):
    return [x if x else "∅" for x in values]

def compute_metrics(frame):
    raw_refs = nonempty([normalize_whitespace(x) for x in frame["reference"]])
    raw_preds = nonempty([normalize_whitespace(x) for x in frame["prediction"]])
    norm_refs = nonempty([normalize_arabic(x) for x in frame["reference"]])
    norm_preds = nonempty([normalize_arabic(x) for x in frame["prediction"]])

    raw_cer = float(jiwer_cer(raw_refs, raw_preds))
    raw_wer = float(jiwer_wer(raw_refs, raw_preds))
    norm_cer = float(jiwer_cer(norm_refs, norm_preds))
    norm_wer = float(jiwer_wer(norm_refs, norm_preds))
    return {
        "samples": int(len(frame)),
        "cer_raw": raw_cer,
        "wer_raw": raw_wer,
        "exact_match_raw": float(np.mean([a == b for a, b in zip(raw_refs, raw_preds)])),
        "cer_normalized": norm_cer,
        "wer_normalized": norm_wer,
        "character_accuracy_from_cer": float(np.clip(1.0 - norm_cer, 0.0, 1.0)),
        "word_accuracy_from_wer": float(np.clip(1.0 - norm_wer, 0.0, 1.0)),
        "exact_match_normalized": float(np.mean([a == b for a, b in zip(norm_refs, norm_preds)])),
        "chrf2_normalized": float(chrf.corpus_score(norm_preds, [norm_refs]).score),
    }

groups = {
    "all_567_mixed_exposure": pred_df,
    "train_seen": pred_df[pred_df["original_split"].eq("train")],
    "heldout_validation_plus_test": pred_df[~pred_df["original_split"].eq("train")],
    "validation": pred_df[pred_df["original_split"].eq("validation")],
    "test": pred_df[pred_df["original_split"].eq("test")],
}

metrics = {name: compute_metrics(frame) for name, frame in groups.items() if len(frame)}
metrics_df = pd.DataFrame(metrics).T
display(metrics_df.style.format({
    "cer_raw": "{:.4f}", "wer_raw": "{:.4f}", "exact_match_raw": "{:.2%}",
    "cer_normalized": "{:.4f}", "wer_normalized": "{:.4f}",
    "character_accuracy_from_cer": "{:.2%}", "word_accuracy_from_wer": "{:.2%}",
    "exact_match_normalized": "{:.2%}", "chrf2_normalized": "{:.2f}",
}))

print("\nReport the TEST row as the cleanest generalization result.")
print("Do not describe the all-567 row as held-out accuracy.")

# ---- notebook cell 16 ----
per_style_rows = []
for style, frame in pred_df.groupby("style"):
    row = {"style": style, **compute_metrics(frame)}
    per_style_rows.append(row)
per_style_df = pd.DataFrame(per_style_rows).sort_values(["samples", "style"], ascending=[False, True])
display(per_style_df)

pred_df.to_csv(WORK_DIR / "quranic_ocr_predictions.csv", index=False, encoding="utf-8-sig")
metrics_df.to_csv(WORK_DIR / "quranic_ocr_metrics_by_exposure.csv", encoding="utf-8-sig")
per_style_df.to_csv(WORK_DIR / "quranic_ocr_metrics_by_style.csv", index=False, encoding="utf-8-sig")
with (WORK_DIR / "quranic_ocr_metrics.json").open("w", encoding="utf-8") as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)

run_info = {
    "base_model": BASE_MODEL,
    "adapter_model": ADAPTER_MODEL,
    "adapter_revision": ADAPTER_REVISION,
    "dataset_repo": DATASET_REPO,
    "dataset_revision": DATASET_REVISION,
    "evaluated_samples": len(pred_df),
    "max_new_tokens": MAX_NEW_TOKENS,
    "deterministic_decoding": True,
    "prompt": OCR_INSTRUCTION,
}
with (WORK_DIR / "run_info.json").open("w", encoding="utf-8") as f:
    json.dump(run_info, f, ensure_ascii=False, indent=2)

archive = shutil.make_archive(
    str(WORK_DIR.parent / "KhattVision_Quranic_Evaluation_Results"),
    "zip",
    root_dir=WORK_DIR,
)
print("Results directory:", WORK_DIR)
print("Downloadable archive:", archive)
