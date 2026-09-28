"""Probe Commons categories: does each exist, and how many files / subcategories does it hold? (read-only)"""

from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from commons_collect import api  # noqa: E402

CANDIDATES = [
    "Quranic inscriptions",
    "Quran verses in architecture",
    "Quranic calligraphy",
    "Ayat al-Kursi",
    "Basmala",
    "Basmala in calligraphy",
    "Thuluth inscriptions",
    "Arabic inscriptions",
    "Arabic inscriptions in mosques",
    "Calligraphy in mosques",
    "Islamic inscriptions",
    "Kufic inscriptions",
    "Surah Al-Ikhlas",
    "Shahada",
    "Hagia Sophia calligraphic roundels",
    "Mihrabs",
    "Inscriptions in Turkey",
    "Arabic calligraphy in Iran",
    "Epigraphy of the Alhambra",
    "Calligraphy of the Blue Mosque",
]

for c in CANDIDATES:
    d = api(action="query", prop="categoryinfo", titles=f"Category:{c}")
    page = d["query"]["pages"][0]
    info = page.get("categoryinfo")
    if page.get("missing") or not info:
        print(f"  --        {c}")
    else:
        print(f"  files={info.get('files', 0):<5} subcats={info.get('subcats', 0):<4} {c}")
