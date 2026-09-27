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
