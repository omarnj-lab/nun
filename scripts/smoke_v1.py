"""M0 smoke test: KhaṭṭVision v1 on 3 held-out DuwatBench images with the notebook's exact prompts.

Prompts, chat-template suffix and image policy are copied from
training/reference/khattvision_v1_notebook.ipynb (cells 3, 16, 19). Writes data/smoke/v1_smoke.json.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from datasets import load_dataset
from peft import PeftModel
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

BASE_MODEL = "unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit"
ADAPTER = os.environ.get("VLM_ADAPTER", "NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA")
ROWS = [212, 79, 565]  # first 3 of v1's fixed 50-image held-out evaluation rows (model card)
MAX_IMAGE_PIXELS = 448 * 448
MAX_IMAGE_SIDE = 896
OUT = Path("data/smoke/v1_smoke.json")

CANONICAL_STYLES = ["Thuluth", "Diwani", "Naskh", "Kufic", "Ruq'ah", "Nasta'liq"]
THEME_LABELS = [
    "dedication",
    "devotional invocation",
    "hadith",
    "names of Allah",
    "names of companions",
    "names of the Prophet",
    "non-religious",
    "personal/place name",
    "quranic",
]
THEME_OPTIONS = json.dumps(THEME_LABELS, ensure_ascii=False)
STYLE_OPTIONS = json.dumps(CANONICAL_STYLES, ensure_ascii=False)

PROMPT_OCR = "اقرأ جميع النصوص العربية الظاهرة في لوحة الخط. أعد النص فقط دون شرح، وافصل المقاطع بسطر جديد."
PROMPT_STRUCTURED = f"""
حلّل لوحة الخط العربي وحدّد أنواع الخط، والتصنيف الموضوعي،
والنصوص العربية ومواقعها.

القيم المسموح بها في styles فقط:
{STYLE_OPTIONS}

يجب أن تكون theme قيمة واحدة فقط من:
{THEME_OPTIONS}

تعليمات إلزامية:
- استخدم أسماء التصنيفات السابقة حرفيًا.
- لا تستخدم مرادفات مثل religious أو Islamic أو Dua أو Quranic.
- استخدم bbox_1000_xywh بصيغة [x, y, width, height].
- يجب أن تكون جميع الإحداثيات أعدادًا صحيحة بين 0 و1000.
- أعد JSON صالحًا فقط.
- لا تضف شرحًا أو Markdown.

البنية المطلوبة:
{{
  "styles": ["Diwani"],
  "theme": "quranic",
  "regions": [
    {{
      "bbox_1000_xywh": [100, 100, 700, 300],
      "text": "النص العربي"
    }}
  ]
}}
""".strip()


def prepare_image_for_model(image: Image.Image) -> Image.Image:
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


def extract_json(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def main() -> None:
    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained(ADAPTER)
    try:
        processor.image_processor.resample = Image.Resampling.BICUBIC
    except Exception:
        pass
    base = AutoModelForImageTextToText.from_pretrained(
        BASE_MODEL, device_map={"": 0}, dtype=torch.bfloat16, low_cpu_mem_usage=True
    )
    model = PeftModel.from_pretrained(base, ADAPTER, is_trainable=False).eval()
    load_s = time.perf_counter() - t0
    mem_after_load = torch.cuda.max_memory_allocated(0) / 2**30
    print(f"loaded in {load_s:.0f}s, {mem_after_load:.1f} GiB allocated")

    @torch.inference_mode()
    def generate(image: Image.Image, instruction: str, max_new_tokens: int) -> tuple[str, float]:
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": instruction}]}]
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        prompt += " to=user<|message|>"
        inputs = processor(
            text=[prompt], images=[[prepare_image_for_model(image)]], add_special_tokens=False, return_tensors="pt"
        ).to("cuda")
        torch.cuda.synchronize()
        t = time.perf_counter()
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, use_cache=True, do_sample=False)
        torch.cuda.synchronize()
        dt = time.perf_counter() - t
        text = processor.tokenizer.batch_decode(out[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        return text[0].strip(), dt

    ds = load_dataset("MBZUAI/DuwatBench", split="train")
    results = []
    for idx in ROWS:
        s = ds[idx]
        ocr, ocr_s = generate(s["image"], PROMPT_OCR, 192)
        raw, st_s = generate(s["image"], PROMPT_STRUCTURED, 512)
        parsed = extract_json(raw)
        valid = isinstance(parsed, dict) and {"styles", "theme", "regions"} <= parsed.keys()
        results.append(
            {
                "row_index": idx,
                "image_id": s["image_id"],
                "gold_text": "\n".join(s["text"]),
                "gold_style": s["style"],
                "gold_theme": s["category"],
                "ocr": ocr,
                "ocr_seconds": round(ocr_s, 2),
                "structured_raw": raw,
                "structured_json_valid": valid,
                "structured_seconds": round(st_s, 2),
            }
        )
        print(f"row {idx}: json_valid={valid} ocr={ocr_s:.1f}s structured={st_s:.1f}s")

    summary = {
        "base": BASE_MODEL,
        "adapter": ADAPTER,
        "gpu": torch.cuda.get_device_name(0),
        "load_seconds": round(load_s, 1),
        "mem_after_load_gib": round(mem_after_load, 2),
        "peak_mem_gib": round(torch.cuda.max_memory_allocated(0) / 2**30, 2),
        "json_valid": f"{sum(r['structured_json_valid'] for r in results)}/{len(results)}",
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
