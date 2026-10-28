# Contributing

Thanks for helping make EPUB reading better on the web.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
```

## Principles

1. **The EPUB is the source of truth.** The converter may change structure and
   presentation, never the prose.
2. **The fidelity gate is non-negotiable.** A build must fail if a word,
   punctuation mark, or paragraph moves.
3. **No runtime LLM or network calls.** The pipeline is deterministic.
4. **Keep the output static.** No Node build step, database, or client-side
   rendering of the book text.
5. **Prefer a small, explicit converter over magic.** If a book has unusual
   markup, add a focused rule and a test.

## Tests

`tests/conftest.py` generates a tiny EPUB on the fly, so tests need no
copyrighted fixture and no network. Add a regression test for every converter
change.

```bash
make test          # Ruff + pytest
make lint
make format
make build         # sdist + wheel
make check-dist    # twine check
```

## Changelog

Add user-facing changes under `## Unreleased` in `CHANGELOG.md`, grouped under
`Added`, `Changed`, `Fixed`, `Security`, or `Upgrade notes`. Write the entry
for users, not for other developers; internal refactors and test-only changes
do not need one. Preview a release section with:

```bash
make release-notes VERSION=0.2.0
```

## Landing site

The public landing page and download page live in `site/` and are built with
Astro. They are separate from the Python package and are not required to build
a book.

```bash
cd site
npm install
npm run dev
npm run build
```

The site self-hosts the reader fonts and the screenshots in `docs/`. Download
buttons resolve the latest GitHub release to direct asset URLs at build time.
The committed `site/src/data/latest-release.json` is refreshed by
`npm run update-release` and before every Pages build. The release workflow
dispatches Pages after publishing a release so the direct links stay current.
Keep the first-launch FAQ in sync with the README when warning behavior
changes.

The Pages workflow publishes the site at `/epub2web/` and the generated demo at
`/epub2web/demo/`. Astro assets and internal links are base-path aware; use
`withBase()` for new root-relative links or files in `public/`.

## Pull requests

- Keep changes focused and explain the book structure they address.
- Include the failing case (without copyrighted text) and the expected result.
- Run `make test`.
- Do not add a copyrighted EPUB or a full generated edition to the repository.

## Reporting issues

A useful report includes:

- Python version and `epub2web --version`
- the command you ran
- the failing page and the fidelity/link output
- a minimal EPUB skeleton or markup sample that reproduces it

Please do not attach books you do not have the rights to share.
