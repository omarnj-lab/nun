# Nūn — run from Linux/WSL (on this Windows box: `wsl make <target>` from the repo folder).
SHELL := /bin/bash
VENV ?= $(HOME)/.venvs/nun
PY := $(VENV)/bin/python
UV ?= uv
TORCH_BACKEND ?= cu128

.PHONY: setup env tier smoke-v1 corpus spotcheck lists index test synth train eval dev deploy lint

setup:  ## env + deps (Python 3.11, CUDA torch, unsloth, dev tools)
	$(UV) python install 3.11
	test -x $(PY) || $(UV) venv --python 3.11 $(VENV)
	VIRTUAL_ENV=$(VENV) $(UV) pip install torch torchvision --torch-backend=$(TORCH_BACKEND)
	VIRTUAL_ENV=$(VENV) $(UV) pip install -e ".[ml,dev]" --torch-backend=$(TORCH_BACKEND)
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

test:
	$(VENV)/bin/pytest -q

corpus:  ## download sources → data/corpus/quran.jsonl + MANIFEST.json (fails on any build check)
	$(PY) -m nun.corpus.build

spotcheck:  ## 20 random ayahs byte-for-byte against QuranEnc's per-aya endpoint
	$(PY) scripts/spotcheck_corpus.py

lists:  ## reviewer drafts: data/lists/{names,dhikr}.draft.jsonl, inscriptions.draft.yaml
	$(PY) scripts/build_lists.py

index synth train eval dev deploy:
	@echo "'make $@' is not implemented yet (see IMPLEMENTATION.md)"; exit 1
