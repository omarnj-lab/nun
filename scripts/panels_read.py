"""Demo panels, step 2: KhaṭṭVision v1 reading of every candidate panel.

Model loading, prompt, chat template and decoding are copied from the Quranic evaluation notebook
(notebookfc4bcd6109.ipynb, cells 8 and 10; also eval/notebooks/khattvision_quranic_eval.py). Only the image
policy differs, as specified: MAX_IMAGE_PIXELS = 896*896, MAX_IMAGE_SIDE = 1344. Greedy decoding.
Readings are appended to data/panels/readings.jsonl after every image; re-running skips panels already read.

    CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. python scripts/panels_read.py
"""

from __future__ import annotations

import copy
import csv
import json
import math
import os
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from unsloth import FastModel  # noqa: E402, I001  (must be imported before torch/transformers)

import torch  # noqa: E402
from PIL import Image  # noqa: E402

ADAPTER_MODEL = "NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA"
ADAPTER_REVISION = "2cdaa0fd967f1a0ac78d044df8930b410dc2b326"
MAX_NEW_TOKENS = 192
MAX_IMAGE_PIXELS = 896 * 896
MAX_IMAGE_SIDE = 1344
PANELS = Path("data/panels")
OUT = PANELS / "readings.jsonl"

OCR_INSTRUCTION = "اقرأ جميع النصوص العربية الظاهرة في لوحة الخط. أعد النص فقط دون شرح، وافصل المقاطع بسطر جديد."


def prepare_image_for_model(image):  # notebook cell 10
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


def main() -> None:
    model, processor = FastModel.from_pretrained(  # notebook cell 8
        model_name=ADAPTER_MODEL,
        revision=ADAPTER_REVISION,
        max_seq_length=4096,  # notebook: 1024; 896² images alone are ~1,024 vision tokens
        load_in_4bit=True,
        use_gradient_checkpointing=False,
        offload_embedding=False,
        token=os.environ.get("HF_TOKEN"),
    )
    FastModel.for_inference(model)
    model.eval()
    assert [n for n, m in model.named_modules() if hasattr(m, "lora_A")], "LoRA adapter not loaded"
    try:
        processor.image_processor.resample = Image.Resampling.BICUBIC
    except Exception:
        pass

    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": OCR_INSTRUCTION}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    prompt += " to=user<|message|>"  # required by the Muse Glimmer template used during fine-tuning

    @torch.inference_mode()
    def predict_ocr(image):  # notebook cell 10
        inputs = processor(
            text=[prompt], images=[[prepare_image_for_model(image)]], add_special_tokens=False, return_tensors="pt"
        ).to(torch.device("cuda:0"))
        generation_config = copy.deepcopy(model.generation_config)
        generation_config.max_length = None
        generation_config.max_new_tokens = MAX_NEW_TOKENS
        generation_config.do_sample = False
        generation_config.use_cache = True
        output_ids = model.generate(**inputs, generation_config=generation_config)
        new_tokens = output_ids[:, inputs["input_ids"].shape[1] :]
        return processor.tokenizer.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()

    panels = list(csv.DictReader((PANELS / "candidates.csv").open(encoding="utf-8")))
    done = set()
    if OUT.exists():
        done = {r["file"] for r in map(json.loads, OUT.open(encoding="utf-8")) if not r.get("error")}
    for p in panels:
        if p["file"] in done:
            continue
        row = {"file": p["file"], "reading": None, "error": None, "seconds": None}
        t = time.perf_counter()
        try:
            row["reading"] = predict_ocr(Image.open(PANELS / "raw" / p["file"]))
        except Exception as exc:  # noqa: BLE001 — record and continue, like the notebook
            row["error"] = f"{type(exc).__name__}: {exc}"
            torch.cuda.empty_cache()
        row["seconds"] = round(time.perf_counter() - t, 2)
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{p['file'][:12]} {row['seconds']:>5}s {'ERROR ' + row['error'] if row['error'] else ''}", flush=True)
    ok = sum(1 for r in map(json.loads, OUT.open(encoding="utf-8")) if not r.get("error"))
    print(f"read {ok}/{len(panels)} panels → {OUT}")


if __name__ == "__main__":
    main()
