"""List pre-labels where the corpus lookup and the model's own verse guess disagree (for a quick human look)."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from label_tool.app import state  # noqa: E402

for cid, s in state().items():
    lab = s["label"]
    if not cid.startswith("rt-") or "DISAGREES" not in lab.get("notes", ""):
        continue
    refs = ", ".join(f"{r['sura']}:{r['aya_from']}-{r['aya_to']}" for r in lab["refs"][:4])
    guess = re.search(r"model guess (\d+:\d+)", lab["notes"]).group(1)
    reading = lab["notes"].split(" · ")[0].removeprefix("model reading: ").replace("\n", " / ")[:80]
    print(f"{cid} corpus=[{refs}] model={guess} | {reading}")
