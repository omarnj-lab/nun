# Sources register

Every external resource the product uses, why, its terms, the required attribution, and its status. **Nothing is used before it is listed here.** Status: ✅ verified (endpoint + terms checked 2026-09-27) · 🟡 usable, one check pending · 🔴 needs a team/reviewer decision before use. This file ships in the public repo as `docs/SOURCES.md` and is part of the submission ("sources log").

---

## 1. Quran text, translations, tafsir

| Resource | Used for | Access | Terms / attribution | Status |
|---|---|---|---|---|
| **QuranEnc** (Rowwad Translation Center / Islamhouse) | Uthmani verse text (`arabic_text` field, Hafs), translations, Tafsir al-Muyassar | `GET https://quranenc.com/api/v1/translation/sura/{key}/{sura}` → `{"result":[{"id","sura","aya","arabic_text","translation","footnotes"}]}` · per-aya: `/translation/aya/{key}/{sura}/{aya}` · list: `/translations/list` (JSON `{"translations":[{key,language_iso_code,version,last_update,title,description}]}`) | Republishing allowed if: **no modification/addition/deletion**; cite **QuranEnc.com** and the **translation version**; keep translator info; use latest versions; no inappropriate ads | ✅ |
| **Tanzil** Quran text | Matching text (`simple-clean`) + cross-check of Uthmani | tanzil.net/download (text types: simple, simple-min, simple-clean, uthmani, uthmani-min; formats txt / txt+aya / xml / sql), v1.1 (2021) | "Copy and distribute **verbatim** copies… changing the text is not allowed"; cite **Tanzil Project** + link tanzil.net | ✅ |
| **Tanzil metadata** | Surah names (ar/en), ayah counts, juz/hizb/page, revelation type | `https://tanzil.net/res/text/metadata/quran-data.xml` (200 OK, 77 KB) | Attribute Tanzil | ✅ |

Chosen translation keys (all on QuranEnc; versions as of 2026-09-27; record the version shown at download time):

| Lang | Key | Version | Translator / publisher | Package status |
|---|---|---|---|---|
| en | `english_saheeh` | 1.1.2 | Saheeh International (Noor International Center) | ✅ listed on quranpedia.net («ترجمة الإنجليزية - صحيح انترناشونال») |
| fr | `french_montada` or `french_rashid` | 1.0.0 / 1.0.3 | Noor International Center / Rachid Maach | 🔴 reviewer picks one and confirms it is a King Fahd Complex edition or listed on quranpedia.net |
| ur | `urdu_junagarhi` | 1.1.3 | Muhammad Junagarhi (printed by the King Fahd Complex) | 🟡 confirm on quranpedia.net |
| id | `indonesian_complex` | 1.0.1 | King Fahd Complex ("The Complex") | 🟡 confirm |
| zh | `chinese_makin` | 1.0.2 | Muhammad Makin (Ma Jian) | 🟡 confirm |
| ar tafsir | `arabic_moyassar` | record | التفسير الميسر (King Fahd Complex) | 🔴 see note below |

**Build notes (M1, 2026-09-27):** Tanzil's simple-clean and uthmani files write the sura-header Basmala at the start of aya 1 of every sura except 1 and 9; the corpus separates it (verse text unchanged, recorded in `data/corpus/MANIFEST.json`). `arabic_moyassar` is served by the QuranEnc API but is not in its published translations list, so it has no version number to cite.

**Tafsir note (decide before Oct 4):** the package approves "sources from the first three centuries or dorar.net/tafseer". Tafsir al-Muyassar is a modern King Fahd Complex work: complete, clean and API-accessible, but not named in the package. Options: (a) ask the organisers (Discord / info@islamicaich.org) whether it's acceptable; (b) use Dorar's «موسوعة التفسير» (dorar.net/tafseer, reachable from the server with a normal user-agent; reuse terms 🔴 unknown) for the curated inscription verses; (c) both, with Dorar shown first where available. Whatever is chosen, the UI names the tafsir and distinguishes its words from the Quranic text.

## 2. Recitation audio (human reciters only)

| Resource | Access | Terms | Status |
|---|---|---|---|
| Mishary Alafasy, per-ayah MP3 via EveryAyah | `https://everyayah.com/data/Alafasy_128kbps/{sss}{aaa}.mp3` (e.g. `020114.mp3`, 200 OK) | 🔴 check the site's usage terms; attribute reciter + source | 🟡 |
| Same files via quran.com CDN | `https://verses.quran.com/Alafasy/mp3/{sss}{aaa}.mp3` (200 OK) | 🔴 check Quran.com / Quran Foundation terms | 🟡 |

Stream from the source (don't rehost) unless the terms allow rehosting. **Never TTS for Quran.**

## 3. Hadith, misconceptions, terminology (chat grounding)

| Resource | Used for | Access | Status |
|---|---|---|---|
| Sahih al-Bukhari / Sahih Muslim via dorar.net/hadith | Curated hadith set (only hadith the reviewer approves, stored with book, number, grading) | dorar.net/hadith (reachable with a normal user-agent; blocks some bots) | 🔴 reuse terms; curate a small set by hand for the demo verses |
| «بينات: أسئلة وأجوبة عن الإسلام» | RAG source for general questions and misconceptions (package-designated) | page dawa.center/file/7937 → PDF `https://dawa.center/storage/files/AMYj6DfmHlSnZ766Zz0VlBNwmYtdwhAl31XMETlT.pdf` | 🟡 designated by the package; confirm redistribution terms before shipping the chunks in the public repo (fetch at build time otherwise) |
| Jamhara dictionary (islamic-content.com/dictionary) | Approved English equivalents for sharia terms (glossary; overrides MT) | HTML pages (200 OK) | 🟡 designated by the package; store only the terms we use, with links |

## 4. Fonts (synthetic data + UI)

All SIL Open Font License 1.1, from `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/<file>` (verified pattern):

| Family | Style role | File(s) |
|---|---|---|
| Amiri, Amiri Quran | Naskh (data) · **Quran text in the UI** | `amiri/Amiri-{Regular,Bold}.ttf`, `amiriquran/AmiriQuran-Regular.ttf` |
| Scheherazade New, Noto Naskh Arabic, Markazi Text | Naskh variety | `scheherazadenew/…`, `notonaskharabic/NotoNaskhArabic[wght].ttf`, `markazitext/MarkaziText[wght].ttf` |
| Aref Ruqaa (+ Ink) | Ruq'ah | `arefruqaa/ArefRuqaa-{Regular,Bold}.ttf` |
| Reem Kufi, Noto Kufi Arabic, Qahiri | Kufic | `reemkufi/ReemKufi[wght].ttf`, `notokufiarabic/…`, `qahiri/…` |
| Noto Nastaliq Urdu, Gulzar | Nasta'liq | `notonastaliqurdu/NotoNastaliqUrdu[wght].ttf`, `gulzar/Gulzar-Regular.ttf` |
| IBM Plex Sans Arabic | **UI text** | `ibmplexsansarabic/IBMPlexSansArabic-*.ttf` |

Thuluth and Diwani: **no open-licensed fonts confirmed.** Cover them with real DuwatBench images (train only) + heavier augmentation; don't use proprietary fonts.

## 5. Datasets and test images

| Resource | Use | Terms | Status |
|---|---|---|---|
| MBZUAI/DuwatBench (HF, 1,272 images; 567 Quranic, 344 devotional, 97 Names of Allah, 140 non-religious) | Training + the v1 50-image held-out comparison | Metadata Apache-2.0; images from Pinterest/archives under their own licenses → **train only, never redistribute** | ✅ |
| Wikimedia Commons | `real-test` set (150–200 real photos, never trained on) | Per-file license from the API (`prop=imageinfo&iiprop=extmetadata`: `LicenseShortName`, `Artist`, `Credit`); keep only CC0 / PD / CC-BY / CC-BY-SA | ✅ |

Useful Commons categories (verified to exist): `Islamic calligraphy` (500+ files), `Thuluth inscriptions`, `Thuluth style`, `Allah in calligraphy`, `﷽`, `Arabic calligraphy`, `Calligraphy of the Ottoman Empire`, `Naskh (script)` (131), `Nastaliq` (67), `Calligraphy of Muhammad`. Walk subcategories via `list=categorymembers&cmtype=subcat`. Send a descriptive `User-Agent`.

## 6. Models

| Model | Role | Link | Status |
|---|---|---|---|
| `unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit` | VLM base (4-bit) | HF | ✅ (per v1 card) |
| `NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA` | v1 adapter (start point for v2) | HF · training code: kaggle.com/code/engomarnajar/notebookf34951354e | ✅ team-owned |
| `NAMAA-Space/Qari-OCR-0.4.0-VL-4B-Instruct` | Fallback VLM for small GPUs | HF | ✅ team-owned |
| `Omartificial-Intelligence-Space/GATE-AraBert-v1` | Arabic embeddings (candidate search) | HF | ✅ team-owned |
| `Omartificial-Intelligence-Space/ARA-Reranker-V1` (or `NAMAA-Space/GATE-Reranker-V1`) | Candidate reranking | HF | ✅ team-owned |
| `Omartificial-Intelligence-Space/Arabic-labse-Matryoshka` | Cross-lingual search (related verses from non-Arabic questions) | HF | ✅ team-owned |
| `NAMAA-Space/NAMAA-Saudi-TTS` | Optional Arabic TTS for **non-Quranic** UI text | HF (MIT) | ✅ team-owned |
| `facebook/dinov2-small` | Global image embedding for panel photo matching (shortlist before SIFT + RANSAC verification) | HF (Apache-2.0) | ✅ |
| `qwen3.6` (Ollama, 36B MoE, Q4_K_M) | Local chat model: default provider for the verse chat (Anthropic `claude-opus-5` selectable) | Ollama library (Apache-2.0) | ✅ |
| `gpt-oss:20b` (Ollama, MXFP4) | Alternative local chat model | Ollama library (Apache-2.0) | ✅ |
| Claude `claude-opus-5` (Anthropic API) | Chat agent + router; zero-shot vision baseline | api.anthropic.com | ✅ needs `ANTHROPIC_API_KEY` |

## 7. Challenge documents (reference only, not redistributed)
`context/participant_guide.pdf`, `context/scientific_package.pdf`, `context/presentation_template.pptx`.
