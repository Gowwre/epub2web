PY ?= python3
RUFF ?= $(shell command -v ruff >/dev/null 2>&1 && echo ruff || echo uvx ruff)

.PHONY: build check test verify links lint lint-js format theme theme-check clean clean-sites

build:
	npm run build

check:
	npm run check

test: check theme-check lint lint-js

verify:
	$(PY) scripts/verify.py

links:
	$(PY) scripts/check_links.py

lint:
	$(RUFF) check epub2web scripts
	$(RUFF) format --check epub2web scripts

lint-js:
	node --check static/assets/app.js
	node --check epub2web/theme/assets/app.js

format:
	$(RUFF) format epub2web scripts

theme:
	$(PY) scripts/sync_theme.py

theme-check:
	$(PY) scripts/sync_theme.py --check

clean:
	$(PY) scripts/clean.py

clean-sites:
	$(PY) scripts/clean.py --sites DontMakeMeThink ThinkingInSystems
