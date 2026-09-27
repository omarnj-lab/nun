"""M1 spot-check: 20 random ayahs from data/corpus/quran.jsonl vs QuranEnc's per-aya endpoint, byte for byte.

The corpus is built from the per-SURA endpoint; this re-fetches through a different endpoint, live, without cache.
Writes data/corpus/SPOTCHECK.json and exits non-zero on any mismatch.
"""

from __future__ import annotations

import json
import random
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from nun.corpus.sources import QURANENC_API, USER_AGENT
from nun.corpus.store import CorpusStore

N, SEED = 20, 20261004


def main() -> None:
    store = CorpusStore()
    sample = random.Random(SEED).sample(store.all(), N)
    rows, bad = [], 0
    for r in sorted(sample, key=lambda r: (r.sura, r.aya)):
        url = f"{QURANENC_API}/translation/aya/english_saheeh/{r.sura}/{r.aya}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        live = json.load(urllib.request.urlopen(req, timeout=60))["result"]
        ok_ar = live["arabic_text"].encode() == r.text_uthmani.encode()
        ok_en = live["translation"].encode() == r.translations["english_saheeh"].text.encode()
        bad += not (ok_ar and ok_en)
        rows.append({"ref": f"{r.sura}:{r.aya}", "arabic_identical": ok_ar, "translation_identical": ok_en})
        print(f"{r.sura:>3}:{r.aya:<3} arabic={'OK' if ok_ar else 'DIFF'} en={'OK' if ok_en else 'DIFF'}")
    report = {"checked_at": datetime.now(UTC).isoformat(timespec="seconds"), "seed": SEED, "n": N, "mismatches": bad}
    Path("data/corpus/SPOTCHECK.json").write_text(
        json.dumps({**report, "rows": rows}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{N - bad}/{N} identical")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
