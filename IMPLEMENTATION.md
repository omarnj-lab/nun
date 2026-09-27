# Implementation plan

Order of work for Claude Code on the GPU server + the human tasks that unblock it. Specs: `SPEC.md`. Rules: `CLAUDE.md`, `RULES.md`.

**Phase tags:** `[PRE]` = may be done before Oct 4 09:00 Riyadh (declared in `PRIOR_WORK.md`, captured by tag `pre-challenge`) · `[BUILD]` = do during Oct 4–6 (scored). **Owner:** 🤖 Claude Code · 👤 team (Omer / Saeed) · 👳 Sharia reviewer.

**Strategy:** get a thin end-to-end version working on **Day 1 by 16:00** (v1 adapter + search + card + basic chat, deployed), then improve each stage. Something complete and live must exist at all times.

---

## Phase 0 · before Oct 4 `[PRE]`

### M0 · Server, repo, access 🤖👤
- Check GPU (`nvidia-smi`), CUDA, disk (≥ 200 GB free), RAM; pick the tier config (`SPEC.md` §6.4) and record it in `PROGRESS.md`.
- Repo skeleton per `CLAUDE.md`; Makefile targets; `.env` from `.env.example`; pre-commit (ruff, gitleaks).
- Python 3.11 env with CUDA torch + Unsloth; download base `unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit` + v1 adapter; pull the Kaggle notebook into `training/reference/`.
- Smoke-test v1 on 3 DuwatBench images with the notebook's exact prompts; record latency + memory.
- **Done when:** `make setup` works on a clean shell; v1 returns valid JSON on 3/3 images; tier chosen; secrets not in git.

### M1 · Corpus `[PRE]` 🤖 (+👳 decisions)
- `make corpus`: QuranEnc (Uthmani + chosen translations + tafsir), Tanzil simple-clean + metadata → `data/corpus/quran.jsonl` + `MANIFEST.json` (versions, timestamps, checksums).
- Normaliser + 30 unit tests (`SPEC.md` §3.3).
- Drafts for 👳: `names.jsonl` (99 Names + sources), `dhikr.jsonl` (~30 common non-Quran inscriptions, each with source + grading), `inscriptions.yaml` (~500 Quran spans, §6.1). Reviewer signs off in `docs/REVIEW_LOG.md`.
- **Done when:** build checks pass (6,236 ayahs etc.); spot-check 20 random ayahs byte-for-byte against quran.com/QuranEnc web; reviewer sign-off recorded (or pending items listed).

### M2 · Source decisions 👤👳
- Choose the fr/ur/id/zh translations and confirm each is a King Fahd Complex edition or listed on quranpedia.net (`SOURCES.md` 🔴/🟡 rows).
- Tafsir decision (Muyassar vs Dorar vs both), ideally with a quick confirmation from the organisers.
- Recitation audio terms (EveryAyah / quran.com); Bayyinat + Jamhara reuse terms.
- **Done when:** no 🔴 left in `SOURCES.md` for anything the MVP uses.

### M3 · Real test set `[PRE]` 🤖👤👳
- 🤖 `scripts/commons_collect.py`: walk the Commons categories in `SOURCES.md` §5, keep CC0/PD/CC-BY/CC-BY-SA photos of real inscriptions, save file + license + author + URL.
- 🤖 `scripts/label_tool` (tiny local web page): shows an image, runs `locate()` on a typed reading, lets the labeller pick/confirm ref ranges, style, theme, or mark "other/unreadable".
- 👤 label 150–200 images (mix: ~60% Quran, ~15% Names/dhikr, ~25% other/non-religious); second person reviews.
- **Done when:** `eval/sets/real-test.jsonl` complete with licenses; none of these images appear anywhere in training data (hash check).

### M4 · Scaffolding only `[PRE]` 🤖
- Empty-but-runnable skeletons: FastAPI app with `/api/health`; React PWA shell with brand tokens, i18n, RTL; synthetic renderer that renders **one** verse in **one** font (proves shaping works on the server); eval harness that runs on 5 images.
- Write `PRIOR_WORK.md` (template in `RULES.md` §5), commit, **`git tag pre-challenge` before Oct 4 09:00** and push the tag (private repo is fine until submission).
- **Done when:** tag exists; `PRIOR_WORK.md` lists everything above.

---

## Phase 1 · build days `[BUILD]`

### Day 1 · Oct 4 — walking skeleton, then data + training

**M5 · Search + verification pipeline (with v1)** 🤖 · 09:00–13:00
- `nun/retrieval/` n-gram index, `locate()` with spans, GATE embeddings, reranker; `nun/vlm/infer.py` for v1 tasks; `/api/scan` end-to-end with a **temporary** gate (v1 reading + alignment only).
- Tests: synthetic noisy readings of 500 random spans (drop/replace 10–30% of letters, split/merge words) → `locate()` top-5 recall ≥ 0.95, top-1 ≥ 0.85.
- **Done when:** `/api/scan` returns a correct card for 3 sample panels; unit tests green.

**M6 · Card + basic chat + deploy** 🤖 · 12:00–16:00
- `/api/verse`, result card UI (verified / partial / uncertain / out_of_scope), recitation player, sources sheet.
- Agent v0: router + grounded answer with citations over the verse documents only (no tools yet); transparency banner; quote guard.
- Deploy (compose + HTTPS); share the link with the team.
- **Done when:** a phone can scan → card → ask 2 questions with citations, over HTTPS. **Checkpoint: this is the fallback submission.**

**M7 · Synthetic dataset** 🤖 · 09:00–16:00 (parallel)
- Full renderer (`SPEC.md` §6.2) for the approved list; sample grid reviewed by a human (Arabic shaping correct, no broken glyphs, text matches label).
- Build task A/B/C JSONL (§6.3), DuwatBench mix, `synth-dev`.
- **Done when:** 15–20k images (or the size the smoke test allows), grid reviewed, JSONL validated (every image exists, every target parses).

**M8 · Train KhaṭṭVision v2** 🤖 · start by 17:00, runs overnight
- 30-step smoke test → final config → full run with checkpoints every ~1 h; log loss + a 50-image dev eval at each checkpoint.
- Fallback trigger: if the run can't finish by Day 2 10:00 → switch to the smaller config or Qari-OCR 4B (tier ≤ 24 GB path).
- **Done when:** a checkpoint beats v1 on `duwat-heldout` CER and has task-B accuracy ≥ 0.9 on `synth-dev`.

### Day 2 · Oct 5 — v2 in the product, evaluation, full agent

**M9 · Integrate v2 + calibrate** 🤖 · 09:00–12:00
- Swap v1 → v2 behind a flag; verification with label probabilities; fit the score model + thresholds on `synth-dev` + a dev split of DuwatBench (**never** on real-test); precision of `verified` ≥ 0.97 on dev.
- **Done when:** gate thresholds committed with the dev-set evidence.

**M10 · Evaluation + baselines** 🤖 · 11:00–16:00
- Run all baselines + Nūn on `real-test` and `duwat-heldout` (`SPEC.md` §10); coverage plot; results table; error analysis (20 failures, categorised).
- **Done when:** `eval/results/<date>/` committed; headline numbers reproducible with one command.

**M11 · Full agent** 🤖👳 · 12:00–20:00
- Tools (`get_verse`, `get_translation`, `get_tafsir`, `search_related_verses`, `search_sources`, `refer_to_human`); Bayyinat + glossary + curated hadith indexes; all guards (`SPEC.md` §9); level routing.
- Agent suite: 12 package cases + 20 verse cases; fix until all checks pass; 👳 reviews every answer and signs off in `docs/REVIEW_LOG.md`.
- **Done when:** suite passes (level correct, referral when required, 0 uncited religious claims, 0 generated Quran text, 0 fabricated hadith), reviewer sign-off.

**M12 · UX pass + user test** 👤🤖 · 16:00–22:00
- Polish states, errors, loading, RTL, the 5 content languages; sample-panels carousel.
- 👤 run the user test (`SPEC.md` §10) with 8–15 volunteers; 🤖 aggregate anonymously; fix the top issues found and log them ("changed because of user tests").

### Day 3 · Oct 6 — harden, publish, submit (portal closes 23:59)

**M13 · Harden + measure cost** 🤖 · 09:00–13:00
- Load test (20 concurrent scans), timeouts, clear error states, warm-up, health checks, uptime monitor; measure cost per 1,000 scans and per 1,000 chat turns.

**M14 · Releases** 🤖👤 · 10:00–15:00
- HF: KhaṭṭVision v2 adapter + model card (method, data, metrics, limits); Khatt-Quran dataset (synthetic + real-test with per-image licenses; **no DuwatBench images**) + dataset card.
- Repo public: README (what/why/architecture/setup/eval results/limits/team), `docs/SOURCES.md`, `PRIOR_WORK.md` (+ "new during Oct 4–6" section), `docs/REVIEW_LOG.md`, licenses; `gitleaks` clean.

**M15 · Deck + video + submit** 👤🤖 · 14:00–22:00, **submit by 22:00**, not 23:59
- Final deck on `context/presentation_template.pptx` (or the Nūn deck in the challenge identity): add real results, the four-levels safety design, cost numbers, user-test results, clearly separating done vs planned.
- Demo video ≤ 2 min: 0:00 problem (reuse the teaser opening) → 0:15 live scans (a Quran panel, a Name of Allah, one "uncertain" case) → 1:00 chat with citations + a fatwa-type referral → 1:35 results + open source → 1:55 logo.
- Submit on the portal; keep the confirmation; test the live link from a phone on mobile data.

---

## After submission
- Keep the service up until at least Oct 22 (final judging), ideally Oct 26. Don't deploy risky changes during judging windows.
- Finalists (Oct 18): prepare the 5-min live demo + 3-min Q&A; rehearse with the live link and a backup screen recording.

## Human task list (start now)
| Task | Who | By |
|---|---|---|
| Submit registration + deck | 👤 Omer | **Sep 29 23:59** |
| Attend the mandatory opening session | 👤 both | Oct 1 |
| GPU server access for Claude Code; disk; stable network | 👤 | Oct 1 |
| `ANTHROPIC_API_KEY`, `HF_TOKEN` (write to NAMAA-Space), Kaggle API token, domain or Cloudflare account | 👤 | Oct 1 |
| Recruit the Sharia reviewer (name them in the deck) + 8–15 user-test volunteers | 👤 | Oct 2 |
| Source decisions (M2) | 👤👳 | Oct 3 |
| Label the real-test set (M3) | 👤 | Oct 3 |
| Review agent answers + content lists | 👳 | Oct 5 |
| Record the video; final deck; submit | 👤 | Oct 6 22:00 |
