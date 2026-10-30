# AGENTS.md

`epub2web` turns an EPUB into a deterministic, static website. These are
instructions for coding agents working in this repository; `README.md`,
`CONTRIBUTING.md`, and `RELEASING.md` remain the user-facing documentation.

## Read first

- `README.md` — behavior, CLI, output contract, limitations.
- `CONTRIBUTING.md` — contribution expectations and changelog rules.
- `RELEASING.md` — tag-driven release and PyPI process.
- `docs/gui.md` — GUI architecture and portable packaging.
- `docs/fonts.md` — bundled fonts, script detection, and per-book font selection.
- `CHANGELOG.md` — user-facing changes, grouped by release.

## Hard invariants

1. **The EPUB is the source of truth.** Never rewrite, summarize, or silently
   drop prose. The converter may change structure and presentation only.
2. **The fidelity gate is non-negotiable.** Do not weaken `verify.py`, bypass it
   in committed workflows, or use `--no-verify`/`--no-links` to make a change
   pass. Fix the converter or renderer instead.
3. **No runtime LLM, network, or remote service.** Building a book must work
   offline and deterministically.
4. **Keep the output static.** No Node build step, database, or client-side
   rendering of book text.
5. **Do not edit generated output by hand.** Fix `generic.py`, `render.py`,
   `templates/`, or `theme/`; never patch a generated `*-site/` or `dist/` tree.
6. **Safety checks stay in place.** Staged publishing, `check_output`,
   `--force` guards, active-content sanitization, and rejection of remote images
   are intentional. Add tests before changing them.

## Verify

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

make test          # Ruff + pytest
make lint
make format
make build         # sdist + wheel
make check-dist    # twine check
```

Useful manual checks:

```bash
make demo EPUB=book.epub
make gui
make gui-portable
make release-notes VERSION=0.2.0
make release-prepare VERSION=0.3.0   # version/changelog only
make release-ship VERSION=0.3.0      # pushes main + tag; explicit release
```

The test suite generates a tiny EPUB fixture in `tests/conftest.py`; no
copyrighted book is required. Add a regression test for every converter or
renderer change.

## Architecture map

- `epub2web/epub.py` — EPUB container reader; no network or prose heuristics.
- `epub2web/models.py` — typed page plans, page parts, and serialized page data.
- `epub2web/labels.py` — front/back matter labels and chapter title parsing.
- `epub2web/dom.py` — cleaned-DOM block inspection and TOC anchor splitting.
- `epub2web/planner.py` — spine document → reading page planning.
- `epub2web/navigation.py` — EPUB TOC → site contents/sidebar tree.
- `epub2web/generic.py` — deterministic EPUB → semantic page extraction.
- `epub2web/text.py` — normalization, text extraction, tokenization, slugs,
  reading-length estimates. Changes here affect the fidelity gate; test them
  carefully.
- `epub2web/fonts.py` — script detection, font-manifest selection, generated
  `@font-face` CSS, and RTL language checks.
- `epub2web/render.py` — Jinja rendering, static assets, search index, sitemap.
- `epub2web/paths.py` — shared route and base-path helpers.
- `epub2web/verify.py` — text/image/structural fidelity gate.
- `epub2web/links.py` — internal link, anchor, image, and duplicate-ID gate.
- `epub2web/cli.py` — CLI orchestration, safety checks, staging/publishing.
- `epub2web/server.py` — local preview server.
- `epub2web/logging.py` — persistent logs, JSONL events, support ZIPs.
- `epub2web/progress.py` — progress protocol shared by CLI, worker, and GUI.
- `epub2web/updates.py` — best-effort GUI update check against GitHub Releases.
- `epub2web/gui.py` — GUI launcher and hidden `--worker`/`--self-test` modes.
- `epub2web/tk_app.py` — Tkinter view; all widget calls stay on the Tk thread.
- `epub2web/controller.py` — toolkit-independent worker process controller.
- `epub2web/worker.py` — worker process; must not import GUI modules.
- `scripts/build_gui.py` — portable PyInstaller bundles.
- `scripts/release_notes.py` — extracts a version section from `CHANGELOG.md`.
- `scripts/release.py` — prepares a version/changelog and ships the release tag.
- `site/` — Astro landing and download site. Self-contained; not part of the
  Python package. Download CTAs point at the latest GitHub release. See
  `site/README.md`.

## Testing rules

- Use `epub_factory`/`tiny_epub` from `tests/conftest.py` for EPUB variants.
- Cover failure behavior, not just the happy path: missing images, remote
  images, broken anchors, empty spines, unsafe output paths, and gate failures.
- Never add a full book, copyrighted text, or generated site to the repository.
- Keep tests offline and deterministic.
- If you change `text.py`, run the fidelity and link tests even when the change
  looks cosmetic.

## GUI and packaging

Local GUI and portable work needs Tk and the build extra:

```bash
pip install -e ".[gui-build]"
```

- The controller and worker must remain toolkit-independent; do not import Tk
  from `controller.py` or `worker.py`.
- The GUI runs in a process; the worker runs in a separate process. Keep
  subprocess cleanup and preview lifecycle behavior intact.
- In frozen builds the worker is the same executable with `--worker`.
  `--self-test` checks that Tk and the view modules were bundled.
- PyInstaller cannot cross-compile. Test portable builds on the target OS; the
  release workflow builds Linux, Windows, and macOS separately.
- New GUI assets must be added to `pyproject.toml` package data and, when
  relevant, the PyInstaller data collection and license notices.

## Changelog and releases

- Add every user-facing change under `## Unreleased` in `CHANGELOG.md`, grouped
  under `Added`, `Changed`, `Fixed`, `Security`, or `Upgrade notes`.
- Write for users, not developers. Internal refactors and test-only changes do
  not need entries.
- Before a release, move `Unreleased` entries into a dated section such as
  `## 0.3.0 - 2026-10-28` and bump `epub2web.__version__`.
  `make release-prepare VERSION=X.Y.Z` does both and leaves a fresh empty
  `Unreleased` section. It refuses an empty `Unreleased` section or a version
  that is not greater than the current one.
- `make release-ship VERSION=X.Y.Z` checks a clean `main` branch, verifies the
  version and changelog section, runs the tests, pushes `main`, and pushes
  `vX.Y.Z`. `scripts/release.py ship` is a dry run unless `--execute` is passed;
  the Make target passes it. Use `--watch` on the script to follow the release
  workflow.
- The release workflow extracts the exact version section and fails before
  building if it is missing or empty. Preview it with
  `make release-notes VERSION=X.Y.Z`.
- Do not create or push tags, create GitHub releases, or publish to PyPI unless
  explicitly asked.
- `publish.yml` and its `pypi` environment are tied to PyPI trusted publishing.
  Do not rename or move that workflow without updating the PyPI publisher. A
  failed publish with `invalid-publisher` means the matching pending publisher
  has not been configured on PyPI.
- Update `THIRD_PARTY_NOTICES.md` when adding dependencies or bundled assets.

## Style

- Python 3.10+; avoid syntax newer than the supported floor.
- Ruff with double quotes; line length is configured at 100.
- Prefer small, focused changes and explicit code over broad refactors.
- Do not add dependencies without a clear need and a packaging/license update.
- Keep package data in sync with `pyproject.toml`, `MANIFEST.in`, and
  `scripts/build_gui.py`.

## Definition of done

- `make test` passes.
- Behavior changes include a regression test.
- User-facing changes have a `CHANGELOG.md` entry.
- Documentation is updated when commands, files, or architecture change.
- No books, generated sites, build outputs, or secrets are committed.
