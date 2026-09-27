# نون · Nūn: Project Plan

**Challenge:** تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي (Islamic AI Challenge 2026)
**Track:** 03, Interactive experiences and learning journeys to introduce Islam (التجارب التفاعلية والرحلة المعرفية للتعريف بالإسلام وتعلمه)
**One line:** Point your phone at Arabic calligraphy, get a verified card (verse, reference, metadata, English translation, recitation), then chat with an agent that answers only from approved sources. When the system is not sure, it says so.

> **Implementation handoff:** `handoff/` holds the engineering spec for Claude Code on the GPU server: `CLAUDE.md` (rules), `SPEC.md` (how it works), `IMPLEMENTATION.md` (milestones + done criteria), `RULES.md` (challenge rules + the scientific package), `SOURCES.md` (verified sources). This file stays the strategy overview.

---

## 1. Key dates

| Date (Riyadh time) | Milestone | Owner action |
|---|---|---|
| **Sep 29, 11:59 PM** | Registration closes | Submit form: track, name, description, idea deck (PPTX + PDF, ≤10 slides, ≤10 MB) |
| Sep 30 | Screening and acceptance | Watch email |
| Oct 1 | Opening session | Attend |
| Oct 2–3 | Workshops (RAG, agentic coding, UX, business models) | Attend RAG + UX |
| **Oct 4, 09:00 → Oct 6, 11:59 PM** | Build days (remote). **Only work done here is scored.** | Build, train, evaluate, submit |
| Oct 7–15 | First-round judging (top 20) | Keep live demo running |
| Oct 18 | Finalists announced | Prepare 5-min pitch + 3-min Q&A |
| Oct 19–22 | Final judging on Zoom | Pitch |
| Oct 26 | Ceremony, Riyadh | |

---

## 2. Problem

- Millions of non-Arabic-speaking visitors see Quran verses, the Names of Allah and supplications written in calligraphy on mosque walls, in museums, at heritage sites and at events such as the Islamic Arts Biennale. They cannot read them.
- General tools fail on artistic scripts. Google Lens and general VLMs misread Thuluth, Kufic and Diwani, and often produce **fluent but wrong** text. For Quranic content that is a reliability problem, not a cosmetic one.
- Calligraphy is one of the most visible faces of Islamic civilization, and today it goes unexplained to the people most curious about it.

**Audience:** non-Arabic-speaking visitors, new Muslims, guides at mosques and museums, and people who introduce Islam (المعرّفون بالإسلام).

---

## 3. Starting point (declared prior work)

| Asset | Status | Note |
|---|---|---|
| [KhaṭṭVision v1](https://huggingface.co/NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA) | Muse Glimmer 30B + LoRA r16, trained on DuwatBench | CER 0.58 · WER 0.77 · exact match 0.38 · style-set 0.76 · theme 0.50 · JSON valid 1.00 · mean IoU 0.71 (50-image held-out set) |
| [DuwatBench](https://huggingface.co/datasets/MBZUAI/DuwatBench) | 1,272 images, Apache-2.0 metadata | 567 Quranic · 344 devotional · 97 Names of Allah · 140 non-religious. Images come from Pinterest and other sources under their own licenses: **train on them, never republish them.** |
| GATE-AraBert, Arabic-Triplet-Matryoshka, ARA-Reranker, GATE-Reranker | Arabic retrieval stack | Candidate search + reranking |
| NAMAA-Saudi-TTS, Qari-OCR | Speech + OCR | Arabic audio; small-model fallback |

These are declared in the submission as prior components. The challenge scores only what is built Oct 4–6.

---

## 4. Core idea: identify, verify or abstain

v1 tries to *read everything*. Nūn only needs to know *which text it is*. The Quran is a closed set of 6,236 verses, and supplications and the 99 Names are small closed sets too. So we change the task:

```
PERCEIVE (our model)
Photo
 → KhaṭṭVision v2: text with [؟] where unreadable + style + theme + regions
 → normalize (strip diacritics, unify alef / ya / ta marbuta, remove tatweel)
 → candidate search in the closed corpus (Quran / Names / supplications, picked by theme):
      char n-gram fuzzy match + GATE embeddings → top-20
 → ARA-Reranker → top-5
 → KhaṭṭVision v2 verification: (image, candidate) → match / partial / no
 → confidence gate: below threshold → abstain ("could not identify reliably" + style only + ask a guide)

EXPLAIN (card)
 → Quran DB lookup → metadata card:
      Uthmani text · surah + ayah · juz · Makki/Madani · topic · addressee · calligraphy style
      English translation (approved, translator named) · transliteration · recitation audio

CONVERSE (LLM agent)
 → chat seeded with the verified verse; the agent answers only through tools:
      get_verse(ref) · get_translation(ref, lang) · get_tafsir(ref, source) · related_verses(ref)
      word_meaning(ref, word) · refer_to_human(topic)
 → guards: Ara-Prompt-Guard on input · citation check on output (every claim maps to a tool result)
      · rulings/fatwa questions → refer_to_human
```

The model never generates Quranic text for the user. Everything shown comes from the verified corpus.

---

## 5. Model: KhaṭṭVision v2

### 5.1 Tasks

| Task | Input → Output | Mix |
|---|---|---|
| **A. Reading with uncertainty** | image → text, `[؟]` for unreadable spans | 40% |
| **B. Verification** (new) | image + candidate text → `match` / `partial` / `no` | 35% |
| **C. Structure** (kept from v1) | image → JSON {styles, theme, regions} | 25% |

- **Task A labels:** occlude, blur or crop parts of synthetic images and replace those spans with `[؟]` in the target.
- **Task B negatives:** (1) verses one or two words apart (e.g. repeated verses in Ar-Rahman), (2) neighbouring verses of the same surah, (3) similar supplications and Names of Allah, (4) random verses. Balance about 1 positive : 1 partial : 2 negatives.

### 5.2 Training settings

| Setting | v1 | v2 |
|---|---|---|
| Init | base | **continue from v1 adapter** |
| LoRA rank | 16 | 32, attention + MLP |
| Image area | 448² max | **≈896² max** + region crops from predicted boxes |
| Max seq length | 1,024 | 1,024 |
| Curriculum | real only | synthetic → real mix, real up-weighted ×2 |
| Epochs | n/a | 1–2 |
| Hardware | Kaggle / Unsloth 4-bit | one 80 GB GPU (A100/H100), Unsloth 4-bit, roughly 6–10 h |

**Fallback:** if the 30B run is slow or unstable, fine-tune Qari-OCR 4B on tasks A + C and use the reranker for verification.

---

## 6. Dataset: Khatt-Quran (community release)

| Split | Content | Size (target) | Released? |
|---|---|---|---|
| `synth-train` | ~500 most-displayed verses + 99 Names + common supplications, rendered per style | 15–20k images | Yes, CC-BY or Apache |
| `duwat-mix` | DuwatBench train images (minus our held-out) | ~1.2k | No (link to original only) |
| `real-test` | Real photos of inscriptions from Wikimedia Commons (public domain / CC), hand-verified, never trained on | 150–200 | Yes, with per-image license |

**Synthetic generator:**
- **Fonts, open-licensed where possible:** Amiri (Naskh), Aref Ruqaa (Ruq'ah), Reem Kufi (Kufic), a Nasta'liq font. **Thuluth and Diwani fonts need a license check before use.**
- **Layouts:** single line, stacked Thuluth-like composition, circular medallion, mirrored, arched band.
- **Surfaces:** marble, wood, glazed tile, gold leaf, painted plaster; procedural textures only, no scraped photos.
- **Camera effects:** perspective warp, blur, glare, low light, partial occlusion, JPEG noise.
- **Labels written by the generator:** exact text, surah:ayah, style, theme, bounding boxes.

**Verse list:** start from verses that appear in DuwatBench's Quranic subset, then add well-known inscription verses (Basmala, Al-Ikhlas, Al-Falaq, An-Nas, Ayat al-Kursi, An-Nur 24:35, Al-Fath 48:29, Al-Isra 17:80, etc.). A reviewer with Sharia knowledge checks the list.

**Text sources:** follow the challenge's scientific package (`handoff/RULES.md` §3): Quran text and translations from King Fahd Complex editions or quranpedia.net-listed translations (via QuranEnc), matching text from Tanzil; details and terms in `handoff/SOURCES.md`.

---

## 7. Evaluation

**Test sets:** `real-test` (main, never trained on) + DuwatBench 50-image held-out set (for comparison with v1).

| Metric | Why it matters |
|---|---|
| Verse-ID top-1 / top-5 | The core function |
| Selective accuracy + coverage | When it answers, is it right? How often does it answer? |
| Hallucination rate | Wrong verse shown with confidence (target ≈ 0) |
| CER / WER | Continuity with v1 |
| Style + theme accuracy | Continuity with v1 |
| Latency per photo | Usability |

**Baselines (same test set):** Claude zero-shot vision (GPT-4o / Gemini if keys exist), base Muse Glimmer, KhaṭṭVision v1, v1 + search, **v2 + search + verification**.

**Reliability tests (for the 15% criterion):** non-religious calligraphy → must not map to a verse; partial or cropped verse → `partial` + shows the full verse with a note; unreadable image → abstain; a verse that is one word off → must not be accepted.

**Learning-journey test (Track 3 criterion):** a small usability test with synthetic personas or volunteers, run without collecting personal data. Measure before/after understanding of the verse's meaning with 3 quiz questions.

---

## 8. App

### 8.0 Agent details
- **LLM:** Claude (`claude-opus-5`, Anthropic API) with a content-level router (أ/ب/ج/د from the scientific package), tools and citations; see `handoff/SPEC.md` §8.
- **Grounding:** RAG index over approved tafsir and translations only. The agent may not answer from its own memory; answers without a tool citation are blocked and regenerated.
- **Scope:** the conversation stays tied to the verified verse and related topics. Rulings, personal religious questions and anything outside the sources → `refer_to_human`.
- **Tests:** a fixed set of questions per demo verse (meaning, context, related verses, a ruling question that must be referred, a prompt-injection attempt that must be blocked).


- **Platform:** mobile-first web app (PWA) + FastAPI on the team's own GPU server (Docker Compose, HTTPS via Caddy or a Cloudflare tunnel); see `handoff/SPEC.md` §12.
- **Screens:**
  1. **Camera / upload**
  2. **Result card:** calligraphy style chip · verse in Uthmani script · surah:ayah · juz · Makki/Madani · topic · English translation + transliteration · Play recitation · confidence badge
  3. **Chat:** "Ask about this verse" opens the agent, with suggested questions (What does it mean? Who is it addressing? Related verses?) and source chips under every answer
  4. **"Not sure" state:** style info + "ask a guide" button
- **Languages at launch:** English, French, Urdu, Indonesian, Chinese (translation availability decides the final list).
- **Privacy:** no account, no photo stored by default, no inference of the user's religion or beliefs (a Track 3 requirement).
- **Sources panel:** every screen shows where the text and translation came from.

---

## 9. Build-day schedule (Oct 4–6)

| When | Model + data | App + eval |
|---|---|---|
| **Day 1 AM** | Render synthetic set; build task A/B/C JSONL | Scaffold PWA + API; load Quran corpus + search index |
| **Day 1 PM → night** | **Start v2 training run** | Search + reranker pipeline working with v1; baselines on test set |
| **Day 2 AM** | Check the checkpoint on the dev set; tune thresholds | Result card with metadata, translations, recitation |
| **Day 2 PM** | Full evaluation: v2 vs baselines | Chat agent + tools + citation check; abstain state; deploy v1 → v2 |
| **Day 3 AM** | Release model + dataset on HF | Reliability + agent test suites; UX pass |
| **Day 3 PM** | Freeze results table | Video (≤2 min), final deck, README, sources log, GitHub public; **submit before 11:59 PM** |

---

## 10. Deliverables checklist (from the guide)

- [ ] Working product, live link (not a prototype)
- [ ] Public GitHub repo: full code, setup docs, licenses, no secrets or personal data
- [ ] Video ≤ 2 minutes
- [ ] Final deck (PDF or PPTX): problem, solution, how it works, value, tech, results, continuation plan
- [ ] Sources log: Quran text, translations, fonts, datasets, models and their licenses, and how each is verified
- [ ] HF releases: KhaṭṭVision v2 adapter, Khatt-Quran dataset, demo Space

---

## 11. Pre-challenge work (before Oct 4, declared as prior)

- [ ] Registration form + idea deck (by Sep 29)
- [ ] Verse list v0 + Sharia review
- [ ] Font license check (especially Thuluth / Diwani)
- [ ] Quran text + translation licenses confirmed
- [ ] Real-test candidate image list from Wikimedia Commons (URLs + licenses)
- [ ] GPU booked for Oct 4–6; Unsloth env tested with the v1 adapter
- [ ] Generator + training script skeletons (declared as starting code)

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| Thuluth still unreadable after tuning | Verification + closed-corpus search don't need a perfect reading; abstain when unsure |
| 30B too slow or costly to serve | Qari-OCR 4B fallback; cache common verses; batch requests |
| Font or translation licenses | Only open fonts / approved translations; log every source |
| Synthetic-only overfitting | Real data up-weighted; the main test set is real photos only |
| GPU availability during build days | Book in advance; keep a second provider ready |

---

## 13. After the challenge (sustainability, 10%)

- **Cost:** one GPU endpoint on demand plus CPU for search and TTS. Estimate cost per 1,000 scans after the build days.
- **Partners:** mosque visitor programs, museums, Islamic arts events, tourism guides. Offer a QR code next to famous inscriptions that opens the verified result directly.
- **Content review:** a Sharia reviewer signs off on the verse list, translations and notes each release.
- **Community:** open dataset and model, with a contribution flow for verified new inscriptions.
