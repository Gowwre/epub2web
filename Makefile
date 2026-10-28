PY ?= python3
RUFF ?= $(shell command -v ruff >/dev/null 2>&1 && echo ruff || echo uvx ruff)

.PHONY: test lint format build check-dist demo gui gui-portable release-notes \
	release-prepare release-ship clean

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

release-notes:
	@test -n "$(VERSION)" || (echo "usage: make release-notes VERSION=0.1.0"; exit 1)
	$(PY) scripts/release_notes.py --version "$(VERSION)"

release-prepare:
	@test -n "$(VERSION)" || (echo "usage: make release-prepare VERSION=0.4.0"; exit 1)
	$(PY) scripts/release.py prepare "$(VERSION)"

release-ship:
	@test -n "$(VERSION)" || (echo "usage: make release-ship VERSION=0.4.0"; exit 1)
	$(PY) scripts/release.py ship "$(VERSION)" --execute

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
