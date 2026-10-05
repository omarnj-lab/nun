# Progress log (append-only)

## 2026-09-27 · M0 · Server, repo, access `[PRE]`

**Machine.** Windows 11 workstation (not a Linux server). Work runs in **WSL2 Ubuntu 24.04**; the repo stays at
`C:\Users\User\Desktop\Nun_handoff\handoff` (= `/mnt/c/Users/User/Desktop/Nun_handoff/handoff`), the venv at
`~/.venvs/nun` and the HF cache in WSL `~/.cache/huggingface`. Run make targets as `wsl make <target>`.
- GPUs: 2 × RTX 5090, 32 GB each, sm_120 (Blackwell), driver 591.86 (CUDA 13.1). GPU 0 drives the display
  (~7 GB in use on the Windows side), so jobs default to GPU 1 (`CUDA_VISIBLE_DEVICES=1`).
- CPU: Intel Core Ultra 9 285K (24 threads). RAM: 127 GB on the host, 62 GB visible in WSL (default WSL cap).
- **Disk: 71 GB free on C:** (97 % used). WSL reports 600 GB free, but its virtual disk lives on C:, so the
  real limit is 71 GB. Below the ≥ 200 GB in the plan. After M0 downloads (~22 GB model + ~12 GB env), about
  35–40 GB are left. See blockers.

**Tier: `a48`** (auto: 2 GPUs totalling 64 GB). Neither card has ≥ 40 GB. For training, the 30B model has to be
split across both cards (v1 was trained split across 2 × T4 16 GB), or it must fit on one 32 GB card. v1
inference fits on one card (21.7 GiB). This choice is **provisional**: the M8 30-step smoke test decides it
(s/step and peak memory on 1 vs 2 GPUs). If it doesn't fit, fall back to `a24` (Qari-OCR 4B).

**Environment (`make setup`, verified from a deleted venv).** Python 3.11.16 (uv), torch 2.11.0+cu128,
transformers **5.15.0**, trl **0.22.2** (both pinned to the v1 notebook), unsloth 2026.9.11, peft 0.21.0,
bitsandbytes 0.50.2, accelerate 1.15.0. Unsloth declares `transformers<=5.5`, but muse_glimmer needs 5.15. Left
alone, uv silently resolves to a broken 2025 Unsloth, so setup force-installs transformers/trl with `--no-deps`,
the same way the notebook does. The `[ERROR] … not documented` lines on import are transformers docstring noise.
Pre-commit (ruff, gitleaks, large-file check) is installed. `.env` was created from `.env.example` and is
gitignored; `ANTHROPIC_API_KEY` and `HF_TOKEN` are already in the Windows user environment (passed into WSL via
`WSLENV=HF_TOKEN`).

**Assets.** Downloaded `unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit` (21 GB), the v1 adapter
`NAMAA-Space/KhattVision-Muse-Glimmer-30B-LoRA`, and DuwatBench (399 MB parquet). The Kaggle notebook
`engomarnajar/notebookf34951354e` is public; it was pulled without credentials into
`training/reference/khattvision_v1_notebook.ipynb`.

**v1 smoke test** (`make smoke-v1` → `data/smoke/v1_smoke.json`). Uses the notebook's exact prompts, chat-template
suffix ` to=user<|message|>` and image policy (448² area, 896 side, bicubic), on the first 3 fixed held-out rows
(212, 79, 565). It loads with transformers + PEFT on 1 × 5090.
- Load 25 s; **21.7 GiB** VRAM (peak same).
- **Structured JSON valid 3/3** ✅. Latency per image: OCR 1.3–3.5 s, structured 4.3–6.6 s.

| row | gold | v1 OCR | style (gold → pred) | theme (gold → pred) |
|---|---|---|---|---|
| 212 | كل شيء هالك إلا وجهه | exact ✅ | Diwani → Thuluth | quranic ✅ |
| 79 | بسم الله الرحمن الرحيم | exact ✅ | Diwani → Thuluth | quranic → devotional invocation |
| 565 | أشهد ألا إله إلا الله وأشهد أن محمدًا عبده ورسوله | **hallucinated** a different dhikr («لا إله إلا الله وحده لا شريك له…»); the structured pass returned Surah al-Ikhlāṣ | Thuluth ✅ | devotional → quranic |

Row 565 is exactly the fluent-but-wrong failure the verification gate (SPEC §4.6–4.7) is designed to catch. Keep
it as a regression example.

**Done-when:** `make setup` on a clean shell ✅ · v1 valid JSON 3/3 ✅ · tier chosen (a48, provisional) ✅ ·
secrets not in git ✅ (`.env` ignored; gitleaks pre-commit hook).

**Blockers / open items**
1. **Disk: 71 GB free vs ≥ 200 GB planned.** This is enough for M1–M4, but not for M7/M8 (15–20k synthetic images,
   checkpoints, a second base model for the a24 fallback, Docker images). Free up C:, add a drive, or move the WSL
   vhdx to another disk before Oct 4.
2. The v1 adapter's HF license is `other` ("subject to the base model terms"; the base is Apache-2.0). State this
   in `PRIOR_WORK.md` (M4).
3. WSL memory is capped at 62 GB. Raise it in `.wslconfig` if training needs more host RAM.
4. No Kaggle credentials exist. They weren't needed (the notebook is public), so `KAGGLE_*` can stay empty.
5. Deployment (M6) from a Windows workstation: use a `cloudflared` tunnel (Docker Desktop is available). The
   machine must stay on through Oct 22.
6. Git identity is set repo-locally (not globally) for the initial commit. Change it if the team wants another
   author.
7. **Leaked HF token (urgent, 👤 Omer):** the public Kaggle notebook `engomarnajar/notebookf34951354e` has a
   hardcoded Hugging Face access token in cell 31 (the push-to-hub cell). gitleaks caught it at commit time.
   Our copy in `training/reference/` is redacted. **Revoke that token on huggingface.co and remove it from the
   Kaggle notebook.** It is publicly readable.

## 2026-09-27 · Disk cleanup (resolves M0 blocker 1)
- C: free 46.8 → **145.2 GB**. With team approval, deleted three Windows HF cache entries unrelated to Nūn:
  `ArabicSpeech/ADI20` (57 GB), `UBC-NLP/NADI_2026_ADI20_micro` (20 GB), `Qwen/Qwen2.5-Omni-7B` (21 GB).
- `uv cache clean` in WSL freed space inside the WSL disk only. Compacting the WSL vhdx (sparse + fstrim, then
  diskpart) reclaimed nothing on C:. Deleting files inside WSL or Docker does not free C:.
- Estimated need for M7/M8 + deploy is ~60–80 GB, so 145 GB is enough. Watch it during synthetic data generation.

## 2026-09-27 · M1 · Corpus `[PRE]`
- `make corpus` → `data/corpus/quran.jsonl` (6,236 records) + `MANIFEST.json`. Sources: QuranEnc (Uthmani text,
  6 translations, al-Muyassar) and Tanzil v1.1 (simple-clean, uthmani, metadata). Raw responses are cached
  byte-for-byte in `data/raw/`; `--offline` rebuilds from the cache.
- **Build checks (all pass; any failure aborts):** 6,236 ayahs · 114 suras · per-sura counts = Tanzil metadata ·
  Uthmani byte-identical to the QuranEnc response and identical across all 7 keys · QuranEnc Uthmani = Tanzil
  Uthmani (normalised) on 6,236/6,236 · no empty texts · juz 1–30 monotonic · Basmala header separated from
  aya 1 of 112 suras.
- **Found and fixed:** Tanzil's text files put the sura-header Basmala inside aya 1 (e.g. 2:1 read «بسم الله
  الرحمن الرحيم الم»). It is now separated from `text_simple`. 1:1 and 27:30 keep theirs (tests added). The
  verse text is unchanged; this is recorded in the manifest.
- **Spot-check** (`make spotcheck`): 20 random ayahs re-fetched live from QuranEnc's per-aya endpoint →
  **20/20 byte-identical** (Arabic + English). Saved to `data/corpus/SPOTCHECK.json`.
- **Normaliser** (`nun/normalize/arabic.py`) per SPEC §3.3, plus folding of Persian/Urdu letter forms (ی ک ہ ۃ
  ھ), after DuwatBench gold text contained «اللہ». 38 cases; 48 tests in total pass.
- **Serving rule** (`nun/corpus/store.py`): only `approved` translations/tafsir are ever returned. Today that is
  English only; fr/ur/id/zh and al-Muyassar are downloaded but withheld until M2 decisions.
- Deviation from SPEC §3.1: `translations` is keyed by QuranEnc key (e.g. `english_saheeh`), not by language,
  because fr has two candidates. The language→key choice lives in `nun/corpus/sources.py`.
- **Reviewer drafts** (`make lists`): `data/lists/names.draft.jsonl` (100), `dhikr.draft.jsonl` (32),
  `inscriptions.draft.yaml` (184 spans). Questions are in `docs/REVIEW_LOG.md`. **Sign-off is pending.**
- DuwatBench finding: 38/567 "quranic" images are not verse text (surah titles/covers, a poetry title, a dhikr).
  Relabel before M7/M8.
- `arabic_moyassar` is served by the QuranEnc API but absent from its published translations list, so it has
  no version number.

**Done-when:** build checks ✅ · 20-ayah spot-check ✅ · reviewer sign-off ⏳ pending (items listed in REVIEW_LOG).

## 2026-09-28 · M3 tooling + M4 scaffolding `[PRE]`
- **M3 collector** (`make commons`): walks the Commons categories from SOURCES §5 (depth 2, 2,188 files at depth
  0 alone) and keeps only CC0/PD/CC-BY/CC-BY-SA (NC/ND/GFDL-only/fair-use rejected; tested), saving ≤1600 px
  renditions + license/author/URL to `data/real/commons/` (gitignored). Candidate count is in the next entry.
- **M3 labelling tool** (`make label` → http://127.0.0.1:8765, local only). Typed reading → corpus
  location (verbatim Uthmani shown for visual confirmation; ambiguous fragments list every reference) or a
  Names/dhikr list match → style + theme → save. Or "other"/"skip". Review mode requires a second, different
  person; a rejection sends the image back with the note. Append-only log `eval/sets/real-test.labels.jsonl`;
  `make realtest` compiles confirmed labels into `eval/sets/real-test.jsonl` and drops near-duplicates
  (pHash ≤ 4) of any DuwatBench/synthetic training image.
- **M4:** `apps/api` (FastAPI, `/api/health`, CORS locked to `WEB_ORIGIN`); `apps/web` (React 19 + Vite + TS
  strict, brand tokens, ar RTL default / en, PWA manifest + icons, no religious text in UI strings; typecheck,
  tests and build pass); `training/synth/render.py --smoke` renders the end of 20:114 from corpus words in
  Amiri with RAQM shaping, visually checked against an unshaped control; `eval/` metrics (SPEC §10, unit-tested)
  + harness: `make eval SET=duwat-heldout SYSTEM=v1-locate LIMIT=5` ran on the GPU (2/3 verses found, 0 confident
  errors, p50 2.1 s/image; a harness check, not a result).
- `nun/vlm/khatt_v1.py`: v1 inference wrapper; a test executes the notebook's prompt cell and asserts the prompts
  and image policy are byte-identical.
- **Bugs found by tests and fixed:** (1) inline comments in `.env.example` were read as values, e.g.
  `WEB_ORIGIN` = "# the web app origin…", which would have broken CORS in production. Comments are now on their
  own lines and blank values mean "default". (2) A hand-typed Uthmani test string differed from the corpus in
  diacritic order. Tests now compare against the corpus, never typed Quran text.
- `docs/PRIOR_WORK.md` written; tag `pre-challenge` created (see below).

## 2026-09-28 · M3 test set redesigned (team decision: A + B)
- **Problem:** Commons has no Quranic-inscription category. The broad categories (399 photos collected) are mostly
  name panels and manuscripts, and there is no time to hand-label 150–200 photos. SPEC §10's single real-test set
  becomes:
- **Set A (headline):** 184 DuwatBench images held out from all training (`eval/sets/duwatbench_split.json`,
  train 906 / validation 182 / test 184, with v1's grouping so near-duplicates never straddle splits).
  v1's exact split (seed 3909) does not reproduce on the current dataset/library versions (no seed of 5,000 puts
  all 50 known held-out rows in test; best 34/50), so the test split is built around the 50 rows v1 certainly
  never saw. **v1-vs-v2 is compared only on those 50 (`duwat-heldout`); other systems on all 184
  (`duwat-test`).** Labels come from DuwatBench's annotators, with verse references by corpus lookup
  (103 Quran, 39 dhikr, 2 Names, 40 other; 58 of the 66 multi-reference labels are the Basmala at 1:1/27:30).
  Devotional-category images are matched to the dhikr list before the Quran (REVIEW_LOG question #2 stays open).
  Spot-check in the label tool (Review mode → "Set A"); a rejection sends the image back for a human label.
- **Set B (real-world photos):** targeted collector (`--targeted`, 50 per category from Basmala, Thuluth
  inscriptions, Mihrabs, Arabic inscriptions, Shahada → 250 photos) + a 60-photo sample of the broad pool. It is
  pre-labelled by `claude-opus-5` vision (`scripts/prelabel_claude.py`, structured output, fallbacks on); the verse
  reference comes from the corpus lookup, and a model-only guess is marked UNVERIFIED. A person confirms in Review
  mode. Compiled rows carry `model_assisted: true` (disclose with results: slight bias towards the Claude baseline).
- **BLOCKED:** the Anthropic API returns "credit balance is too low" (5 trial calls, $0 spent). Estimated cost for
  ~310 images: ~$15 (unmeasured; the script prints measured cost after `--limit 5`).
- Gold-reading upper bound on set A (search + temporary gate only, no vision): top-1 1.0, selective accuracy 0.83,
  confident-error rate 0.5% (1/184), abstention 0.93. This shows what the M5 gate must fix, not a result.

## 2026-09-29 · Set B pre-labelled
- New API key stored in `.env` only (gitignored; the script loads it with override). 309 Commons images
  (250 targeted + 59 broad) pre-labelled by `claude-opus-5`: 0 failures, **$9.81 measured** (≈ $0.032/image).
- Result: 43 Quran · 44 dhikr · 18 Names · 112 other · 92 auto-skipped (86 not calligraphy/unreadable,
  6 identifiable person). 8 Quran labels flagged WEAK (fragment occurs in > 4 places), 1 UNVERIFIED (model guess).
- Locator fixes found by reviewing the trial output, re-derived from the saved outputs at no API cost:
  line-by-line location (a Basmala header no longer hides the verse, e.g. 19:1–2); per-line fuzzy matching
  for spelling variants (رحمة vs the rasm رحمت); the model's layout notes «(…)» and «label:» are stripped; lines
  found in > 12 places («الله», «رسوله») are ignored. 7 new tests (68 total).
- Next (people): Review mode → Set B, confirm/reject; `make realtest` compiles confirmed labels.

## 2026-10-03 · Photo-matching test (PLAN_NOW, [PRE])
- `nun/match/matcher.py`: DINOv2-small shortlist → RootSIFT + RANSAC → accept if ≥ 20 inliers AND ≥ 40% centre
  coverage. `scripts/match_test.py`: 150 Commons collection photos, 450 simulated visitor photos (easy/medium/hard),
  793 unknown images (Commons + internal FIC).
- Result: right panel 100% / 98.7% / 92.7%, wrong panel 0; unknowns accepted 3/793, all three verified by eye as the
  same physical panel (another photo / crop), so 0 genuine false matches. p50 0.42 s.
- Found and fixed: inlier counts alone accepted 42 unknowns (shared ornamental frame templates, chance matches on
  text pages); the centre-coverage check fixed it. Details: `eval/results/2026-10-02/photo_matching/FINDINGS.md`.
- Still needed: the team's own repeat photos (`data/match_test/real_queries/<collection-stem>__*.jpg`) to replace
  the simulated ones.

## 2026-10-03 · Team panels + real photos; pre-challenge snapshot
- `real_test.zip` → `data/real_test/` (git-ignored; the zip moved there too). 21 team panels added to the
  collection; all 21 references valid in the corpus.
- Real phone photos: 5/5 correct (Ayat al-Kursi ×2 right, 93:5 right but narrowly: 40 inliers / 0.44 coverage,
  3:170 right, unknown 48:1 rejected). Simulated with 171 panels: 100 / 98.2 / 94.2%, 0 wrong; team panels 21/21.
- Git audit: no FIC, DuwatBench, shop or real_test images tracked; analysis CSVs (private-dataset predictions)
  git-ignored; analysis code + Quran JSON committed (needed by the panel scripts).
- M1 corpus rebuilt with all checks passing; M4 skeleton tests + build pass; PRIOR_WORK.md updated for PLAN_NOW.

## 2026-10-04 · Day 1 [BUILD] · backend: collection, scan, verse card, chat v0
- Product collection `data/collection/` (git-ignored): 19 panels = 18 demo artworks + real_ayat_alkursi
  (`can_show_publicly = yes`); references validated against the corpus. Commons/FIC/DuwatBench/testing-only stay out.
- Matcher: per-panel text box (coverage counted inside it; default middle 60%).
- `/api/scan` (photo in memory only → matcher → card, or "uncertain": never a verse without a match),
  `/api/verse` (corpus-only card: Uthmani text, surah name/number, juz, Makki/Madani, Saheeh International,
  EveryAyah recitation, sources), `/api/chat`, `/admin` + admin API (HTTP Basic), web app served same-origin,
  per-IP rate limits, matcher warm-up at start.
- Chat v0 (`nun/chat/`): local `qwen3.6` via Ollama in WSL (shares the Windows model files; port 11435) by
  default, Claude `claude-opus-5` selectable. Documents D1 Arabic, D2 approved translation, D3 surah facts;
  router A–D (+ keyword safety net for personal rulings → always referral); guards: Quran-quote replacement,
  hadith removal, citation retry → safe fallback. No tafsir yet (none approved).
- Smoke (real models): demo panel photo → 20:114 card; unknown photo → uncertain; chat answers cite [D1–D3];
  riba-loan question → level D + referral (local had said "out of scope": fixed, tested). Claude ≈ 6 s,
  local ≈ 50 s per answer. 86 tests pass.

## 2026-10-04 · Day 1 [BUILD] · web app, admin tool, live on HTTPS
- Web app (React/Vite/TS, ar RTL default + en, brand tokens): camera/upload (downscaled to 1600 px in the browser)
  → scanning → verse card (Uthmani text in Amiri Quran with ayah markers, surah/ayah/juz/Makki-Madani chips,
  Saheeh International translation + version, EveryAyah recitation, sources) or "couldn't identify" with tips and
  "ask a guide" → chat (AI disclosure banner, suggested questions, Local/Claude switch, "AI-generated" label,
  expandable citations, referral card). Served by the API (single origin).
- Admin `/admin` (HTTP Basic, user admin, ADMIN_PASSWORD in .env): photo + drag a text box + verse preview
  from the corpus → add; list/remove; the matcher is rebuilt on change and uses the text box for coverage.
- `scripts/ops/serve_public.sh`: Ollama (if needed) + uvicorn + Cloudflare quick tunnel (no account).
- Public-link check (`scripts/ops/public_smoke.py`): the team's real phone photo of the Ayat al-Kursi panel →
  2:255 card in 2.2 s (1,253 inliers, coverage 0.94); a photo not in the collection → "uncertain"; two questions
  → cited answers from the local model (≈ 1.5 s each when warm).
- Found: one answer cited [D3] for "known as Ayat al-Kursi", which D3 does not contain → Day 2: citation-
  faithfulness check (each cited sentence must be supported by the cited document).

## 2026-10-04 — Day 1: chat crash fix + brand/deck redesign
- **Chat white page fixed.** A `useEffect` returned `scrollIntoView(...)`; recent Chrome returns a Promise from it, React called that as cleanup and crashed (`destroy_ is not a function`). Effect now uses braces. Checked in headless Chromium (`scripts/ops/ui_check.py`, phone + desktop): no page errors.
- **Redesign to Nun_Brand.pdf + the NUN.pdf deck.** Brand tokens (green #1F5E57, lens gold #C9A04A, ink, paper), IBM Plex Sans Arabic UI, Amiri Quran for verses only. Home = camera viewfinder with gold corners + shutter; scanning = photo + gold sweep + «جارٍ التعرّف على الخط…» pill.
- **Result screen.** Desktop (≥ 960 px): verse info on the reading-start side (right in Arabic), chat on the other half. Info = visitor photo with the matched panel's boundary in gold (matcher projects the panel corners through the RANSAC homography; `/api/scan` returns `panel.polygon`), chips «✓ تم التحقق من المطابقة» · «قرآني», Quran text, translation quote with translator/version, tiles السورة / رقم الآية / الجزء / النزول / التلاوة ▶ استمع (plays the ayahs in order), sources line. Phone: same card, then «اسأل عن هذه الآية» opens the chat full-screen.
- **Chat panel like deck p.7.** Header (thumb, «البقرة 2:255 · تم التحقق», mark), AI banner, Local/Claude switch, user bubbles teal, answers white with citation chips (نص المصحف / Saheeh Intl. / Tanzil; tap shows the cited text + link), referral bubble cream with dashed gold border, «شرح مولَّد» label. `[Dn]` markers no longer shown in the text.
- **Quran text rendering.** QuranEnc's `arabic_text` uses the KFGQPC encoding (U+065E etc.) → empty boxes in Amiri Quran. Corpus now also stores Tanzil's verbatim Uthmani (`text_uthmani_tanzil`, Basmala header separated incl. the بِّسْمِ variant of 95:1/97:1); the card's `text_display` and chat D1 use it. Build check: 6,236/6,236 ayahs agree with QuranEnc after normalisation. SOURCES.md updated.
- `scripts/ops/restart_api.sh`: rebuild web + restart API only; the public tunnel link stays the same.
- Tests: 86 passed; ruff clean.
- Still open (Day 2): local model makes unsupported claims next to citations (e.g. wrong juz) and the quote guard leaves visible placeholders → citation-faithfulness check next.

## 2026-10-04 — Landing page redesign (user: "make UI super attractive")
- New landing modelled on the NUN.pdf cover: track pill, full «نون» lockup, headline with the key phrase highlighted, ﴿نٓ وَٱلۡقَلَمِ…﴾ fetched from the corpus via `/api/verse/68/1` (not typed into the UI), lead text, CTAs «صوّر لوحة» (camera) / «ارفع صورة», and «جرّب بلوحة مثال» which scans `sample.jpg` end-to-end (for judges without a panel at hand).
- Collage of three real collection panels (tilted, floating) with gold viewfinder corners, scan sweep and a «تم التحقق · طه ١١٤» result chip; faint eight-point-star lattice behind the hero.
- Trust row (Mushaf text verbatim · human recitation · photos not stored), three "how it works" cards, and a scrolling strip of the 18 demo panels (`apps/web/public/panels/`, 480 px copies of `can_show_publicly = yes` panels only).
- Scanning screen shows live progress steps (reading → searching → verifying).
- Checked in headless Chromium, phone + desktop, local and via the public link: sample → card 20:114, no page errors. 86 tests pass.

## 2026-10-04 — KhaṭṭVision text regions, "touch to read", recitation player
- **KhaṭṭVision in the app.** `apps/vision/server.py` runs the team's v1 model (Muse-Glimmer-30B 4-bit + LoRA, same prompt as the HF Space) on GPU 0 as an internal service (127.0.0.1:8001; ~25 s load, ~6–7 s per demo panel; output capped at 320 tokens). `serve_public.sh` starts it.
- **`POST /api/regions`** (optional enrichment, after the card): text boxes in the visitor's photo + predicted script style. `nun/vlm/regions.py` parses the structured output (tolerates truncation) and aligns each region's reading to a span of the verified verse words (rapidfuzz ≥ 70). **The reading never leaves the server**; only boxes + word indices do (test enforces it). The card never depends on it; if the service is down → `{available: false}`.
- **Novel feature: touch to read.** Region boxes in gold with numbered badges; tapping a region highlights its words in the Quran text (corpus text), tapping a word highlights its region. Style chip «خط الثلث», labelled as a KhaṭṭVision estimate in the sources line.
- **Recitation player back, visible.** Play/pause, seek bar, time, reciter, ayah counter, live equaliser; the ayah being recited (Arabic + translation) is highlighted.
- Checked in headless Chromium: demo panel → 1 region, 4 words lit; real wall photo → 3 regions. 93 tests pass.

## 2026-10-05 — Clickable gallery + chat in any language (voice in/out)
- **Gallery:** the moving strip of the 18 demo panels is now a row of buttons ("جرّبها"); a click runs a real scan of that panel. All 18 small copies match (253–1,252 inliers). The strip keeps moving slowly even when the OS asks for reduced motion (it pauses on hover).
- **Chat in any language.** The router returns any ISO 639-1 code (sanitised; Urdu and Persian decided by their letters, since models call them "Arabic"); the answer, banner, not-found, out-of-scope, hadith and referral messages come back in that language (fixed texts for 11 languages in `nun/chat/languages.py`, English fallback). Outside Arabic/English the model must present the meaning as an explanation based on the approved English translation, not as an official translation, and says so.
- **UI:** reply-language picker (Auto + 20 languages; Auto shows what was detected), language tag on each answer, banner in the visitor's language, 🔊 read-aloud of answers (browser speech synthesis; anything marked ﴿…﴾ or carrying Quranic diacritics is skipped, so no synthetic voice recites Quran), 🎤 voice input (browser speech recognition, where supported).
- Browser test (`scripts/ops/ui_multilang.py`, via the public link): gallery click → 97:1; French, Urdu and Turkish questions answered in French / اردو / Türkçe; no page errors. 96 tests pass.

## 2026-10-05 — Smoother UI, learning journey, understanding check, «بينات», answer checker, LLM choice
- **Lag fixed.** Gallery fade mask on a moving layer, equaliser height and scan-line `top` animations repainted every frame; now compositor-only (transform/opacity), gallery pauses off-screen. Idle work ≈ 0 layouts / 3 s (`scripts/ops/ui_perf.py`). Server was already fast (scan 0.8 s).
- **Continue the journey** (`nun/journey.py`, `/api/journey`): previous/next ayah verbatim + other collection panels of the same surah ("the next ayah, on another panel"), one tap scans it.
- **Understanding check** (Track 03 criterion): guess the meaning *before* the translation is revealed (3 approved translations as options), then «اختبر فهمك» (meaning, surah, Meccan/Medinan; all from approved data). `/api/quiz/result` stores anonymous counts only (no id/IP, hour-rounded time) in git-ignored `data/quiz/`; `/api/quiz/stats` aggregates pre-guess vs post-quiz accuracy. Discovery passport in the visitor's browser only.
- **Visuals:** "Why are we sure?" draws 48 verified point pairs between the collection panel and the visitor's photo (matcher returns them); "Where is it in the Quran?" shows 114 surahs (Meccan/Medinan, height ∝ ayahs) and 30 juz with this verse marked; live chat status (searching sources → writing → checking each sentence).
- **«بينات» grounding** (package source, 263 questions; pypdf, fetched at build time, not committed): BM25 over question + similar phrasings + short answer, query from the router's Arabic search phrase. Hadith allowed only from a «بينات» document naming al-Bukhari/Muslim.
- **Answer checker** (`nun/chat/verify.py`): numbers must appear in the cited documents; numbers next to "juz/cüz/الجزء/پارہ…" must equal the verse's juz; a judge call drops sentences the cited documents don't state. Visitors only see checked text.
- **LLM choice** (`eval/chat_eval.py`, 28 questions: 12 verse, 12 official RULES §3.5, 4 trick/multilingual; rubric judge Claude — note self-grading bias for the Claude row):
  | model | rubric | official | median s |
  |---|---|---|---|
  | claude-opus-5 | 94.6% (96.4% with low effort + local router) | 10/12 | 10.7 → 6.2–8.4 s live |
  | TuwaiqAI-Instruct (local) | 78.6% | 8/12 | 2.7 |
  | qwen3.6 (local) | 76.8% | 9/12 | 2.5 |
  | gpt-oss:20b (local) | 26.8% | 2/12 | 8.2 |
  → default `CHAT_PROVIDER=anthropic`, router on local qwen3.6 (`ROUTER_PROVIDER=local`), `ANSWER_EFFORT=low`. The UI no longer names or switches the model.
- **Recognition comparison** prepared (`eval/recognition_compare.py`); KhaṭṭVision on the 195 internal images: 34.9% exact (Naskh 83%), answered 68%, precision 52%. External models wait for (a) an OpenAI key and (b) the team's OK to send the internal images to OpenAI/Anthropic (the script refuses without `--allow-external`).
- Tests: 101 pass.

## 2026-10-05 — Recognition comparison (team approved sending the 195 internal images to OpenAI/Anthropic for evaluation only)
- Results: `eval/results/2026-10-05/recognition_compare.md` (numbers only). Nūn deployed: 0 wrong verses on 195 panels outside its collection. KhaṭṭVision v1 34.9% correct / 32.8% wrong; GPT-5.5 57.9% / 35.4%; Claude Opus 5 84.6% / 10.3%. Two-source agreement: 1–3% wrong overall, 0% on Naskh.
- Also today: edge/browser cache headers, 1280 px uploads, Explore tabs (journey / quiz / map / why), sticky ask bar on phones; jank test (`scripts/ops/ui_jank.py`) shows 60 fps at 4× CPU throttling.

## 2026-10-05 — Reading path: KhaṭṭVision at the centre (PLAN_NOW step 2)
- Flow: photo → collection match (instant, verified) → otherwise **KhaṭṭVision reads the panel** (structured: style, theme, text regions) → nearest Quran passage (`nun/retrieval/verse_search.py`, 1–3-ayah windows, 3-gram candidates, rapidfuzz) → **gate** (`nun/reading.py`) → card «قرأها نموذج KhaṭṭVision · تطابق ٪» with the Mushaf text (never the model's reading), or an honest answer showing what the model saw (style, theme, boxes).
- Gate, from the 195-panel internal set: theme must be "quranic"; script must be Naskh (on ornate scripts the model can write a fluent real verse from memory — e.g. a 3:170 panel read as 16:53 with score 100 — which no score threshold catches; on Naskh: 0 wrong at score ≥ 90 + line agreement); ≥ 90 over the strongest line, not just the Basmala, no strong line pointing elsewhere. Calibration of the model's *own* style/theme predictions over all 195 images is running (`analysis/v1_verse_id/structured_run.py`).
- Checks: rendered Naskh panel 39:53 (not in the collection) → read 39:53 at 100%; three real out-of-collection photos (Kufic/Thuluth) → "not sure" with style + boxes, no verse. Tests: reading gate (6), alignment fix (reading longer than the verse).

## 2026-10-05 — Reading path, model-first for every script + independent check
- User: the HF Space read a camera photo correctly but the app declined it (my Naskh-only gate). Now: KhaṭṭVision reads first (same model, prompt and 512-token limit as the Space) → nearest passage, corrected to the Mushaf text → an independent check (Claude, run in parallel, never sees our reading) must name the same place → card «قرأها نموذج KhaṭṭVision · وأكّدها تحقق مستقل». Without the check: strict Naskh gate.
- Measured on 195 panels: 25% identified, 1.0% wrong (vs 29.7% wrong with no check). Live: 93:5 Kufic ✓, 48:1 Thuluth ✓, 3:170 declined (model alone said 16:53).
- Every reading-path decision is logged (status, reason, style, candidate, check, timings; no image). Privacy line updated: out-of-collection photos also go to the checker, not stored.
