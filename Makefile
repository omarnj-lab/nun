# Nūn — run from Linux/WSL (on this Windows box: `wsl make <target>` from the repo folder).
SHELL := /bin/bash
VENV ?= $(HOME)/.venvs/nun
PY := $(VENV)/bin/python
UV ?= uv
TORCH_BACKEND ?= cu128

.PHONY: setup env tier smoke-v1 corpus spotcheck lists commons label realtest review-export review-import render-smoke dev-api dev-web index test synth train eval deploy lint

setup:  ## env + deps (Python 3.11, CUDA torch, unsloth, dev tools)
	$(UV) python install 3.11
	test -x $(PY) || $(UV) venv --python 3.11 $(VENV)
	VIRTUAL_ENV=$(VENV) $(UV) pip install torch torchvision --torch-backend=$(TORCH_BACKEND)
	VIRTUAL_ENV=$(VENV) $(UV) pip install -e ".[ml,api,dev]" --torch-backend=$(TORCH_BACKEND)
	VIRTUAL_ENV=$(VENV) $(UV) pip install --no-deps "transformers==5.15.0" "trl==0.22.2" "torchao>=0.16.0"
	test -f .env || cp .env.example .env
	$(VENV)/bin/pre-commit install
	$(PY) scripts/check_env.py
	@if [ -f apps/web/package.json ]; then cd apps/web && npm ci; fi

env:    ## print GPU / CUDA / library versions and the chosen tier
	$(PY) scripts/check_env.py

smoke-v1:  ## KhaṭṭVision v1 on 3 DuwatBench images (M0)
	CUDA_VISIBLE_DEVICES=$${CUDA_VISIBLE_DEVICES:-1} $(PY) scripts/smoke_v1.py

lint:
	$(VENV)/bin/ruff check . && $(VENV)/bin/ruff format --check .

test:  ## python tests + web tests
	$(VENV)/bin/pytest -q -p no:warnings
	cd apps/web && bash -lc 'source ~/.nvm/nvm.sh >/dev/null 2>&1; npm test --silent && npm run typecheck --silent'

SET ?= duwat-heldout
SYSTEM ?= v1-locate
eval:  ## make eval SET=duwat-heldout|real-test SYSTEM=v1-locate|gold-reading [LIMIT=5]
	CUDA_VISIBLE_DEVICES=$${CUDA_VISIBLE_DEVICES:-1} $(PY) -m eval.run --set $(SET) --system $(SYSTEM) $(if $(LIMIT),--limit $(LIMIT))

render-smoke:  ## M4: render one verse in one font (proves Arabic shaping)
	$(PY) -m training.synth.render --smoke

dev-api:  ## API on :8000
	$(VENV)/bin/uvicorn apps.api.main:app --reload --port 8000

dev-web:  ## PWA on :5173 (proxies /api to :8000)
	cd apps/web && bash -lc 'source ~/.nvm/nvm.sh >/dev/null 2>&1; npm run dev'

corpus:  ## download sources → data/corpus/quran.jsonl + MANIFEST.json (fails on any build check)
	$(PY) -m nun.corpus.build

spotcheck:  ## 20 random ayahs byte-for-byte against QuranEnc's per-aya endpoint
	$(PY) scripts/spotcheck_corpus.py

lists:  ## reviewer drafts: data/lists/{names,dhikr}.draft.jsonl, inscriptions.draft.yaml
	$(PY) scripts/build_lists.py

commons:  ## M3: collect CC0/PD/CC-BY(-SA) calligraphy photos from Wikimedia Commons
	$(PY) scripts/commons_collect.py

label:  ## M3: labelling tool on http://127.0.0.1:8765 (local only)
	$(VENV)/bin/uvicorn scripts.label_tool.app:app --host 127.0.0.1 --port 8765

realtest:  ## M3: compile reviewed labels → eval/sets/real-test.jsonl (+ leakage check)
	$(PY) scripts/compile_realtest.py

review-export:  ## M1: Sharia review spreadsheet → docs/review/Nun_content_review.xlsx
	PYTHONPATH=. $(PY) scripts/review_sheet.py export

review-import:  ## M1: import the filled review spreadsheet (approved items → final lists + REVIEW_LOG)
	PYTHONPATH=. $(PY) scripts/review_sheet.py import

index synth train deploy:
	@echo "'make $@' is not implemented yet (see IMPLEMENTATION.md)"; exit 1
