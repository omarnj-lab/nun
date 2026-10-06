# ن Nūn · نون

**Photograph Arabic calligraphy → see the verse exactly as in the Mushaf → listen → ask in any language.**

Nūn is an AI guide for mosques, museums and homes, built for the *AI in the Service of Islamic Content Challenge 2026*
(Track 03 — interactive experiences that introduce Islam).

- **Live app:** https://sussex-bringing-roger-washer.trycloudflare.com
- **Our model:** [Nūn Vision 30B LoRA](https://huggingface.co/Omartificial-Intelligence-Space/Nun-Vision-30B-Lora) — open weights,
  fine-tuned to read Arabic calligraphy (text, script style, theme, text regions)

## What it does

1. **Recognise the panel.** Panels in the collection are matched instantly (DINOv2 shortlist + SIFT/RANSAC verification).
   Any other panel is **read by Nūn Vision**, matched to the nearest passage of the whole Quran, and shown only if an
   independent check names the same place. Otherwise Nūn says so — it never guesses a verse.
2. **The verse card.** Quran text verbatim from the approved Mushaf text (never written by a model), approved translation
   with the translator's name, human recitation, surah facts — and the recitation glows across the visitor's own photo.
3. **Ask.** A chat that answers in the visitor's language from approved sources only (the verse documents and the
   package's «بينات» Q&A book), checks every sentence against its citation, never invents a hadith, and refers personal
   rulings (fatwa) to scholars.
4. **Learn.** Guess the meaning before reading, a 3-question understanding check (anonymous counts only), the next verse
   on another panel, where the verse sits in the Quran, and the *Nūn Lab* page showing the model at work.

## Architecture

```
browser (React, RTL/LTR) ─HTTPS─► FastAPI  apps/api      :8000  scan · verse · chat · lab · quiz
                                     ├── matcher (DINOv2 + SIFT, GPU 1)
                                     ├── Nūn Vision  apps/vision  :8001  (30B 4-bit + LoRA, GPU 0, ~22 GB)
                                     ├── chat model  Claude (Anthropic API) · local fallback via Ollama
                                     └── corpus      Quran text, translation, metadata, «بينات»
```

## Deploy

**Needs:** Linux (or WSL2) · Python 3.11 · Node 20 · NVIDIA GPU(s): ~24 GB for Nūn Vision + ~8 GB for the matcher and
the local router model · an Anthropic API key.

```bash
# 1. Python + the GPU stack
python3.11 -m venv ~/.venvs/nun && source ~/.venvs/nun/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -e ".[ml]" uvicorn

# 2. Data (downloaded from the original sources; nothing is redistributed here)
python -m nun.corpus.build              # Quran text (QuranEnc + Tanzil), translation, metadata → data/corpus/
python -m nun.chat.bayyinat --fetch     # «بينات» Q&A book → data/raw/bayyinat/

# 3. Web app
cd apps/web && npm ci && npx vite build && cd ../..

# 4. Settings
cp .env.example .env                    # set ANTHROPIC_API_KEY and ADMIN_PASSWORD

# 5. Run everything (Ollama router, Nūn Vision, API, public HTTPS tunnel) with a watchdog
bash scripts/ops/install_ollama_wsl.sh  # once: Ollama + the local router model (qwen3.6)
# serve_forever.sh expects the venv at ~/.venvs/nun and cloudflared at ~/.local/bin/cloudflared
bash scripts/ops/serve_forever.sh       # public link → data/public_url.txt
```

Or run the two services directly:

```bash
CUDA_VISIBLE_DEVICES=0 PYTHONPATH=. uvicorn apps.vision.server:app --host 127.0.0.1 --port 8001
CUDA_VISIBLE_DEVICES=1 PYTHONPATH=. uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
```

The demo collection (19 panels the team may show publicly) is in `data/collection/`; add panels at `/admin`.

## Sources and attribution

| Source | Used for | Terms |
|---|---|---|
| [QuranEnc.com](https://quranenc.com) | Saheeh International translation (v1.1.2), Uthmani text cross-check | verbatim, cite QuranEnc and the version |
| [Tanzil Project](https://tanzil.net) | Uthmani Quran text shown in the app, surah metadata | verbatim copies, attribute Tanzil |
| [EveryAyah.com](https://everyayah.com) | Mishary Rashid Alafasy recitation (streamed, not rehosted) | attribute reciter and source |
| «بينات: أسئلة وأجوبة عن الإسلام» (Osoul Center, [dawa.center](https://dawa.center/file/7937)) | chat grounding for general questions | cited and linked, not redistributed |
| [MBZUAI/DuwatBench](https://huggingface.co/datasets/MBZUAI/DuwatBench) | training data of Nūn Vision | images not redistributed |
| Muse Glimmer 30B (Unsloth 4-bit) | base model of Nūn Vision | Apache-2.0 |
| facebook/dinov2-small · Qwen3.6 (Ollama) · Claude (Anthropic API) | matcher embeddings · local router · chat and independent check | Apache-2.0 · Apache-2.0 · API terms |

Fonts: IBM Plex Sans Arabic, Amiri Quran (SIL OFL 1.1).

## Team

Omer Nacar · Saeed Al-Zahrani
