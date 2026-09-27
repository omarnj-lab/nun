"""Read-only lookup over data/corpus/quran.jsonl. The only way the app reads Quran text."""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

from nun.corpus.models import QuranRecord, TranslationText
from nun.corpus.sources import TAFSIR, TRANSLATIONS


class CorpusStore:
    def __init__(self, path: Path | str = "data/corpus/quran.jsonl") -> None:
        self.path = Path(path)

    @cached_property
    def _by_ref(self) -> dict[tuple[int, int], QuranRecord]:
        with self.path.open(encoding="utf-8") as f:
            recs = (QuranRecord.model_validate(json.loads(line)) for line in f)
            return {(r.sura, r.aya): r for r in recs}

    def __len__(self) -> int:
        return len(self._by_ref)

    def get(self, sura: int, aya: int) -> QuranRecord:
        try:
            return self._by_ref[(sura, aya)]
        except KeyError:
            raise KeyError(f"no ayah {sura}:{aya}") from None

    def range(self, sura: int, aya_from: int, aya_to: int) -> list[QuranRecord]:
        return [self.get(sura, a) for a in range(aya_from, aya_to + 1)]

    def all(self) -> list[QuranRecord]:
        return list(self._by_ref.values())

    def translation(self, sura: int, aya: int, lang: str) -> tuple[str, TranslationText] | None:
        """Approved translation for `lang`, or None. Pending/undecided translations are never returned."""
        for key, info in TRANSLATIONS.items():
            if info["lang"] == lang and info["status"] == "approved":
                return key, self.get(sura, aya).translations[key]
        return None

    def tafsir(self, sura: int, aya: int) -> tuple[str, TranslationText] | None:
        """Approved tafsir, or None while the tafsir decision (SOURCES.md §1) is open."""
        for key, info in TAFSIR.items():
            if info["status"] == "approved":
                return key, self.get(sura, aya).tafsir[key]
        return None
