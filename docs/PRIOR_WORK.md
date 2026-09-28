# Prior work (declared before the build days)

**Starting version:** git tag **`pre-challenge`** (annotated; its message records the commit and the time in Riyadh).
Everything in the repository at that tag existed before **2026-10-04 09:00 (Riyadh, UTC+3)** and is **not** claimed
as challenge work. Only commits after the tag are the work of the build days (Oct 4–6), listed in the last
section at submission.

## Components that existed before this repository

| Component | State before Oct 4 | Owner / license | Evidence |
|---|---|---|---|
| KhaṭṭVision v1 LoRA (`NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA`) | Released Aug 2026; rank-16 adapter; DuwatBench held-out CER 0.583 | Team (Omer Nacar). HF license field: "other" (use subject to the base model's terms, Apache-2.0) | HF model card; fine-tuning notebook kaggle.com/code/engomarnajar/notebookf34951354e (copy in `training/reference/`, one leaked token redacted) |
| Muse Glimmer 30B, 4-bit (`unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit`) | Third-party base model | meta-models / Unsloth, Apache-2.0 | HF model card |
| GATE-AraBert-v1, ARA-Reranker-V1, Arabic-labse-Matryoshka | Released | Team (Omartificial-Intelligence-Space), HF | HF model cards |
| Qari-OCR-0.4.0-VL-4B | Released (fallback VLM) | Team (NAMAA-Space), Apache-2.0 | HF model card |
| NAMAA-Saudi-TTS | Released (not used for Quran, ever) | NAMAA-Space, MIT | HF model card |

## Built in this repository before the tag (Sep 27 – Oct 3)

Milestones M0–M4 of `IMPLEMENTATION.md` (all tagged `[PRE]`). Commit history up to the tag is the evidence.

| Area | What exists | Where |
|---|---|---|
| M0 environment | Makefile (`setup`, `env`, `smoke-v1`), Python 3.11 env (torch cu128, transformers 5.15.0, trl 0.22.2, unsloth), pre-commit (ruff, gitleaks), GPU tier check, v1 smoke test (3/3 valid JSON) | `Makefile`, `pyproject.toml`, `scripts/check_env.py`, `scripts/smoke_v1.py` |
| M1 corpus | Quran corpus builder from QuranEnc + Tanzil with build checks and manifest; Arabic normaliser; read-only store that serves approved translations only; 20-ayah spot-check | `nun/corpus/`, `nun/normalize/`, `scripts/spotcheck_corpus.py`, `data/corpus/MANIFEST.json` |
| M1 reviewer drafts | Draft lists of Names, dhikr and inscription spans (machine-checked against the corpus; not yet signed off) | `scripts/build_lists.py`, `data/lists/*.draft.*`, `docs/REVIEW_LOG.md` |
| Simple fragment locator | Exact word-aligned + fuzzy (rapidfuzz) location of a fragment in the corpus, used by the list builder, labelling tool and the eval baseline. **Not** the SPEC §4.5 candidate search (n-gram index + GATE embeddings + ARA-Reranker), which is build-days work (M5) | `nun/corpus/fragment.py` |
| M3 test-set tooling | Wikimedia Commons collector (license-filtered); local labelling + second-person review tool; compile step with a perceptual-hash leakage check against training images | `scripts/commons_collect.py`, `scripts/label_tool/`, `scripts/compile_realtest.py` |
| M3 test-set labels | Whatever the team has labelled by the tag (count recorded in `eval/sets/real-test.report.json` at tag time) | `eval/sets/` |
| M4 scaffolding | FastAPI app with `/api/health` only; React PWA shell (brand tokens, ar/en i18n, RTL, manifest), with no scan, card or chat; v1 inference wrapper using the notebook's prompts; one-verse synthetic render proving Arabic shaping; eval metrics + harness run on 5 images (temporary gate) | `apps/api/`, `apps/web/`, `nun/vlm/khatt_v1.py`, `training/synth/`, `eval/` |

**Explicitly NOT built before Oct 4** (build-days work, per `IMPLEMENTATION.md` Phase 1): the SPEC §4 scan pipeline
(v2 prompts, VLM verification with label probabilities, n-gram/embedding/reranker search, calibrated gate),
`/api/scan`, `/api/verse`, `/api/chat`, the Claude agent, router, tools and guards, the result card and chat UI,
the full synthetic renderer and dataset, KhaṭṭVision v2 training, calibration, evaluation runs and baselines on
real-test, deployment, releases, deck and video.

## Third-party data and resources used (terms in `SOURCES.md`)
QuranEnc (verbatim republishing with attribution), Tanzil v1.1 (verbatim, attributed), DuwatBench (metadata
Apache-2.0; images used for training/eval only, never redistributed), Wikimedia Commons (per-file CC0/PD/CC-BY/
CC-BY-SA, attributed), Google Fonts (SIL OFL 1.1).

## New during Oct 4–6
_Filled at submission: `git log pre-challenge..HEAD` summarised by milestone._
