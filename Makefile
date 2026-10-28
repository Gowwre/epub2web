PY ?= python3
RUFF ?= $(shell command -v ruff >/dev/null 2>&1 && echo ruff || echo uvx ruff)

.PHONY: test lint format build check-dist demo gui gui-portable clean

test: lint
	$(PY) -m pytest

lint:
	$(RUFF) check epub2web tests scripts
	$(RUFF) format --check epub2web tests scripts

format:
	$(RUFF) format epub2web tests scripts

build:
	$(PY) -m build

check-dist: build
	$(PY) -m twine check dist/*

demo:
	@test -n "$(EPUB)" || (echo "usage: make demo EPUB=book.epub"; exit 1)
	$(PY) -m epub2web "$(EPUB)" --serve

gui:
	$(PY) -m epub2web.gui

gui-portable:
	$(PY) scripts/build_gui.py

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
