.PHONY: help run reload test lint format clean

PY ?= python

help:
	@echo "run     - start the app (python -m uvicorn backend.app.main:app)"
	@echo "reload  - start with auto-reload (development)"
	@echo "test    - run pytest"
	@echo "lint    - ruff check + format check"
	@echo "format  - ruff format"
	@echo "clean   - remove __pycache__ and .pytest_cache"

run:
	$(PY) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

reload:
	$(PY) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

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
