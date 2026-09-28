"""The v1 prompts and image policy must be byte-identical to the fine-tuning notebook (SPEC §5)."""

import json
from pathlib import Path

from PIL import Image

from nun.vlm import khatt_v1

NB = Path("training/reference/khattvision_v1_notebook.ipynb")


def notebook_ns() -> dict:
    cells = [
        "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        for c in json.loads(NB.read_text())["cells"]
    ]
    prompts_cell = next(c for c in cells if c.startswith("THEME_LABELS = ["))
    ns: dict = {"json": json, "math": __import__("math"), "Image": Image}
    ns["CANONICAL_STYLES"] = ["Thuluth", "Diwani", "Naskh", "Kufic", "Ruq'ah", "Nasta'liq"]  # notebook cell 9
    ns["MAX_IMAGE_PIXELS"], ns["MAX_IMAGE_SIDE"] = 448 * 448, 896  # notebook cell 3
    exec(prompts_cell.split("def normalize_bbox_xywh")[0], ns)  # PROMPTS + prepare_image_for_model
    return ns


def test_prompts_identical_to_notebook() -> None:
    ns = notebook_ns()
    assert khatt_v1.PROMPT_OCR == ns["PROMPTS"]["full_ocr"]
    assert khatt_v1.PROMPT_STRUCTURED == ns["PROMPTS"]["structured"]


def test_image_policy_identical_to_notebook() -> None:
    ns = notebook_ns()
    for size in [(3000, 2000), (500, 400), (100, 4000), (448, 448), (2000, 2001)]:
        img = Image.new("RGB", size)
        assert khatt_v1.prepare_image_for_model(img).size == ns["prepare_image_for_model"](img).size
