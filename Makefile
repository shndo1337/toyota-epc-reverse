PYTHON := .venv/bin/python
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: install extract import run test lint typecheck format check benchmark

install:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements-dev.lock.txt
	$(PYTHON) -m pip install --no-deps -e .

extract:
	$(PYTHON) -m epc.extract

import:
	$(PYTHON) -m epc.importer

run:
	$(PYTHON) -m uvicorn --factory epc.api:create_app --host $(HOST) --port $(PORT)

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

check: lint typecheck test

benchmark:
	$(PYTHON) scripts/benchmark.py --url http://$(HOST):$(PORT)
