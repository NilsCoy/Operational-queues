.PHONY: help install venv run reload test lint format clean

IP ?= 127.0.0.1
PORT ?= 8000

PY ?= python
VENV ?= venv
ifeq ($(OS),Windows_NT)
    VENV_PY := $(VENV)/Scripts/python.exe
    VENV_PIP := $(VENV)/Scripts/pip.exe
else
    VENV_PY := $(VENV)/bin/python
    VENV_PIP := $(VENV)/bin/pip
endif

help:
	@echo "install - create venv, install dependencies and start the app"
	@echo "venv    - create venv and install dependencies only"
	@echo "run     - start the app (python -m uvicorn backend.app.main:app)"
	@echo "reload  - start with auto-reload (development)"
	@echo "test    - run pytest"
	@echo "lint    - ruff check + format check"
	@echo "format  - ruff format"
	@echo "clean   - remove __pycache__ and .pytest_cache"

install: venv
	$(VENV_PY) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

venv:
	$(PY) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt

run:
	$(PY) -m uvicorn backend.app.main:app --host $(IP) --port $(PORT)

reload:
	$(PY) -m uvicorn backend.app.main:app --host $(IP) --port $(PORT) --reload

test:
	$(PY) -m pytest backend/tests -v

lint:
	$(PY) -m ruff check backend
	$(PY) -m ruff format --check backend

format:
	$(PY) -m ruff format backend

clean:
	$(PY) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PY) -c "import shutil; shutil.rmtree('.pytest_cache', ignore_errors=True)"
