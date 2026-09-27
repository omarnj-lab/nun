"""Corpus sources and their approval status (mirrors SOURCES.md §1–2; update both together)."""

from __future__ import annotations

QURANENC_API = "https://quranenc.com/api/v1"
TANZIL_DOWNLOAD = "https://tanzil.net/pub/download/index.php?quranType={type}&outType=txt-2&agree=true"
TANZIL_METADATA = "https://tanzil.net/res/text/metadata/quran-data.xml"
AUDIO_ALAFASY = "https://everyayah.com/data/Alafasy_128kbps/{sura:03d}{aya:03d}.mp3"
USER_AGENT = "nun-corpus-build/0.1 (+https://github.com/NAMAA-Space; Islamic content challenge 2026)"

# QuranEnc translation keys downloaded into the corpus. Status: approved | pending (🟡) | undecided (🔴).
# Only `approved` entries may be shown to users (enforced by nun.corpus.store).
TRANSLATIONS: dict[str, dict[str, str]] = {
    "english_saheeh": {"lang": "en", "translator": "Saheeh International", "status": "approved"},
    "french_montada": {"lang": "fr", "translator": "Noor International Center", "status": "undecided"},
    "french_rashid": {"lang": "fr", "translator": "Rachid Maach", "status": "undecided"},
    "urdu_junagarhi": {"lang": "ur", "translator": "Muhammad Junagarhi", "status": "pending"},
    "indonesian_complex": {"lang": "id", "translator": "King Fahd Complex", "status": "pending"},
    "chinese_makin": {"lang": "zh", "translator": "Muhammad Makin (Ma Jian)", "status": "pending"},
}
TAFSIR: dict[str, dict[str, str]] = {
    "arabic_moyassar": {"lang": "ar", "title": "التفسير الميسر", "status": "undecided"},
}

EXPECTED_AYAHS = 6236
EXPECTED_SURAS = 114
