# Changelog

## Unreleased

- Re-running a command for an existing epub2web site now refreshes it automatically instead of failing with an “output already exists” error. Unrelated folders are still refused.
- Add a cross-platform Tkinter desktop GUI (`epub2web-gui`) with a toolkit-independent worker controller, preview lifecycle controls, and PyInstaller worker-mode support.
- Preserve escaped source text that resembles markup, repair missing `#fnN`/`#ffnN` footnote anchors, and normalize malformed external links produced by print conversions.
- Report both fidelity and internal-link gate failures in the desktop GUI.
- Refresh the desktop GUI with the reader's paper palette, custom typography, source/output cards, status indicator, metadata-aware title, custom build console scrollbar, and app icon.
- Add per-image, per-page, render, verification, and link-check progress reporting, with a determinate GUI progress bar and milestone log lines.
- Add `make gui-portable` and a release workflow that builds self-contained desktop artifacts: a single Windows `.exe`, a macOS `.dmg`, and a Linux AppImage or portable tarball, with packaged smoke tests, checksums, and third-party license notices.
- Add a tag-driven **Release** workflow that validates `vX.Y.Z` against the package version, builds the Python and portable artifacts, creates the GitHub release, and dispatches PyPI publishing.

## 0.1.0 — 2026-10-26

- First public release.
- Deterministic EPUB 2/3 → semantic HTML → static site pipeline.
- Token-level and character-level fidelity gate plus internal link gate.
- Built-in search index; no Node or external search service.
- Light/dark theme, responsive reading layout, TOC, figures, notes, index support.
- One-command local preview with `--serve`.
- `--base-path` support for GitHub Pages and other subpath hosting.
- Staged, atomic output: failed builds leave an existing site untouched.
- `--force` safety checks for destructive output paths.
- Per-page image-count gate and link gate for assets and ARIA references.
- Actionable failures for missing, invalid, and remote images; data-URI image support.
- Sanitization of untrusted EPUB markup and safe JSON-LD metadata escaping.
- Nested navigation, structural containers, preformatted text, definition lists, and MathML are preserved.
- Persistent run diagnostics: human-readable logs, JSONL events, fidelity/link/summary artifacts, and `--log-dir`/`--log-file`.
- Preserve Calibre-style body-level TOC anchors and improve part/front/back matter detection for books without numbered chapters.
- Failure support ZIP with README, logs, JSONL events, summary, and gate reports; `--report-dir` control.
