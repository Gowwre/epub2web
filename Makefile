PY ?= python3
RUFF ?= $(shell command -v ruff >/dev/null 2>&1 && echo ruff || echo uvx ruff)

.PHONY: test lint format build check-dist demo clean

test: lint
	$(PY) -m pytest

lint:
	$(RUFF) check epub2web tests
	$(RUFF) format --check epub2web tests

format:
	$(RUFF) format epub2web tests

build:
	$(PY) -m build

check-dist: build
	$(PY) -m twine check dist/*

demo:
	$(PY) -m epub2web "$(EPUB)" --serve

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
