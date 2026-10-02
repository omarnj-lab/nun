PLAN_NOW.md overrides IMPLEMENTATION.md and SPEC.md where they differ.

# نون · Nūn

Point a phone at Arabic calligraphy (mosques, museums, heritage sites) → Nūn identifies **which** Quran verse / Name of Allah / supplication it is, verifies it against a closed trusted corpus, shows a card (verse, reference, approved translation in the visitor's language, human recitation), then lets the visitor chat with an agent that answers **only from approved sources**. When unsure, it abstains and refers to a human guide.

Built for **تحدي الذكاء الاصطناعي في خدمة المحتوى الإسلامي 2026**, Track 03 (interactive experiences to introduce Islam). Team: Omer Nacar (AI), Saeed Al-Zahrani.

**Read before working:** `SPEC.md` (how it works, contracts) · `IMPLEMENTATION.md` (milestones, done-criteria) · `RULES.md` (challenge rules, scientific package, judging) · `SOURCES.md` (every data source + license). Log progress in `PROGRESS.md` (append-only, dated).

---

## Non-negotiable rules

### Content integrity (the product's core promise)
1. **Never generate, complete, correct or paraphrase Quranic text.** Every Quran string shown to a user comes verbatim from the corpus (`data/corpus/quran.jsonl`, sourced per `SOURCES.md`). Models only *identify* and *verify*; they never write verses.
2. **Never use TTS or any synthetic voice to recite the Quran.** Recitation = licensed human reciter audio only. TTS is allowed for non-Quranic UI text/explanations.
3. **No hadith without a source and an approved grading** (Bukhari/Muslim or dorar.net grading, per `RULES.md`). If none is available: say no matching evidence was found. Never fabricate.
4. **Follow the four content levels (أ/ب/ج/د) in `RULES.md`.** Level د (personal fatwa / individual ruling) → general information + referral, never a ruling.
5. **Separate scripture from generated text** in the UI: Quran/hadith/tafsir quotes are visually distinct and cited; AI explanations are labelled as generated and cite what they are based on.
6. **Abstain over guessing.** Low confidence → "could not identify reliably" + calligraphy style only + "ask a guide".
7. **Transparency:** the chat states it is an AI assistant built on approved sources, not a mufti or scholar.

### Data, privacy, licensing
8. Only synthetic or fully anonymised data. No real user photos, chats or logs in the repo, datasets or model training. Photos are processed in memory and not stored.
9. No inference or classification of the user's religion, beliefs or sensitive attributes.
10. Every external resource must be listed in `SOURCES.md` with its license/terms and attribution **before** it is used. Unclear license → don't use it; ask the team.
11. DuwatBench images are third-party (Pinterest etc.): **train on them, never redistribute them** (not in the public repo, not in the HF dataset).
12. No secrets in git. Keys live in `.env` (see `.env.example`). The repo becomes public.

### Challenge rules
13. **Only work done Oct 4 09:00 → Oct 6 23:59 (Riyadh, UTC+3) is scored.** Anything built earlier is "prior work": it must be listed in `PRIOR_WORK.md` and captured by the git tag `pre-challenge` before Oct 4 09:00. Milestones are tagged `[PRE]` (allowed before) or `[BUILD]` (do during the challenge days). Do not start `[BUILD]` work early unless the team explicitly says so.
14. The final product must be **complete and working** (not a prototype), reachable at a live HTTPS link through the judging period (until at least Oct 22).

---

## Architecture (details in SPEC.md)

```
PWA (React, RTL/LTR) ──HTTPS──> FastAPI (GPU server)
                                 ├─ /api/scan  → VLM "KhaṭṭVision v2" (read + structure) → candidate search (char n-grams + GATE embeddings)
                                 │               → ARA-Reranker → VLM verification → confidence gate → verified | partial | uncertain
                                 ├─ /api/verse → corpus card (Uthmani text, ref, juz, Makki/Madani, translations, recitation URL)
                                 └─ /api/chat  → router (content level أ-د) → Claude agent + tools + citations → guards → SSE stream
```

## Repo layout
```
apps/api/        FastAPI service (scan, verse, chat), Dockerfile
apps/web/        React + Vite + TypeScript PWA
nun/             python package: corpus/, normalize/, retrieval/, vlm/, verify/, agent/, guards/
data/            (gitignored) raw downloads, built corpus, synthetic data, test sets
training/        synthetic generator, JSONL builders, Unsloth training scripts, configs per GPU tier
eval/            eval harness, baselines, results/ (committed: metrics + plots, never images)
scripts/         one-off utilities (downloads, labelling tool, export)
brand/           logo + tokens (from the handoff)
docs/            SOURCES.md, PRIOR_WORK.md, model/dataset cards, demo-video script
```

## Commands (keep these working; add to a Makefile)
```
make setup        # env + deps (Python 3.11, CUDA torch, unsloth, api + web deps)
make corpus       # download sources → data/corpus/*.jsonl (+ checksums)
make index        # build n-gram + embedding indexes
make test         # pytest (unit + pipeline) + web tests
make synth N=...  # render synthetic calligraphy dataset
make train CFG=training/configs/<tier>.yaml
make eval SET=real-test MODEL=...   # writes eval/results/<date>/
make dev          # api + web locally
make deploy       # docker compose up -d (api, web, proxy)
```

## Conventions
- Python 3.11, type hints, `ruff` + `pytest`. Pure functions for normalisation/retrieval with unit tests. Config via pydantic-settings + `.env`.
- Frontend: TypeScript strict, React, i18n keys (never hard-coded strings), RTL for Arabic UI. Quran text font: Amiri Quran; UI font: IBM Plex Sans Arabic. Light surfaces only (brand tokens in `SPEC.md` §12).
- Claude API: model `claude-opus-5`, Anthropic Python SDK. Load the **claude-api** skill before writing any Claude code; do not guess SDK signatures.
- Large artefacts (models, datasets) go to Hugging Face under `NAMAA-Space`, never git.
- Every milestone ends with its "Done when" checks from `IMPLEMENTATION.md` passing, a `PROGRESS.md` entry, and a commit.
- Ask the team (don't decide alone) on: religious-content choices, licenses, anything user-facing in Arabic that makes a religious claim, spending money, deploying publicly.
