"""Download the OFL fonts listed in SOURCES.md §4 into data/fonts/ (gitignored; fetched at build time)."""

from __future__ import annotations

import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {  # file → style role (SOURCES.md §4). M4 needs only Amiri; M7 extends this list.
    "amiri/Amiri-Regular.ttf": "Naskh",
    "amiriquran/AmiriQuran-Regular.ttf": "Naskh (Quran)",
}
DEST = Path("data/fonts")


def ensure(rel: str) -> Path:
    dest = DEST / Path(rel).name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(BASE + rel, headers={"User-Agent": "nun-fonts/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
        lic = BASE + rel.split("/")[0] + "/OFL.txt"
        with urllib.request.urlopen(urllib.request.Request(lic, headers={"User-Agent": "nun-fonts/0.1"})) as r:
            (DEST / f"{dest.stem}.OFL.txt").write_bytes(r.read())
    return dest


if __name__ == "__main__":
    for rel in FONTS:
        print(ensure(rel))
