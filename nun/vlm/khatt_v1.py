"""KhaṭṭVision v1 inference: the notebook's exact prompts, chat-template suffix and image policy.

Copied from training/reference/khattvision_v1_notebook.ipynb (cells 3, 16, 19). Used by the M0 smoke test and the
eval harness baseline (v1 reading + corpus search). The v2 tasks (careful reading with [؟], verification) are M5+.
"""

from __future__ import annotations

import json
import math
import os
import time

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from PIL import Image  # noqa: E402

BASE_MODEL = "unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit"
ADAPTER = os.environ.get("VLM_ADAPTER", "NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA")
MAX_IMAGE_PIXELS = 448 * 448
MAX_IMAGE_SIDE = 896

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


class KhattV1:
    """Base 4-bit Muse Glimmer + the v1 LoRA on one GPU (≈ 21.7 GiB)."""

    def __init__(self, adapter: str = ADAPTER, device: int = 0) -> None:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.torch = torch
        t0 = time.perf_counter()
        self.processor = AutoProcessor.from_pretrained(adapter)
        try:
            self.processor.image_processor.resample = Image.Resampling.BICUBIC
        except Exception:
            pass
        base = AutoModelForImageTextToText.from_pretrained(
            BASE_MODEL, device_map={"": device}, dtype=torch.bfloat16, low_cpu_mem_usage=True
        )
        self.model = PeftModel.from_pretrained(base, adapter, is_trainable=False).eval()
        self.device = device
        self.load_seconds = time.perf_counter() - t0

    def generate(self, image: Image.Image, instruction: str, max_new_tokens: int) -> tuple[str, float]:
        torch = self.torch
        messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": instruction}]}]
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        prompt += " to=user<|message|>"
        inputs = self.processor(
            text=[prompt], images=[[prepare_image_for_model(image)]], add_special_tokens=False, return_tensors="pt"
        ).to(f"cuda:{self.device}")
        torch.cuda.synchronize()
        t = time.perf_counter()
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, use_cache=True, do_sample=False)
        torch.cuda.synchronize()
        dt = time.perf_counter() - t
        text = self.processor.tokenizer.batch_decode(out[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        return text[0].strip(), dt

    def read(self, image: Image.Image) -> tuple[str, float]:
        return self.generate(image, PROMPT_OCR, 192)

    def structure(self, image: Image.Image) -> tuple[dict | None, str, float]:
        raw, dt = self.generate(image, PROMPT_STRUCTURED, 512)
        return extract_json(raw), raw, dt
