# Changelog

All notable, user-facing changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- Add a public Astro landing site and download page, with a first-launch FAQ for Windows SmartScreen and macOS Gatekeeper warnings. The Pages workflow publishes the landing page at the project root and moves the live demo to `/demo/`.
- Add a dedicated changelog page with a GitHub link for every published release.

### Changed

- Download buttons now point directly at the current release’s Windows, macOS, and Linux files instead of the GitHub release page. The Pages build resolves the latest assets, and a new release refreshes the download page automatically.

## 0.2.0 - 2026-10-28

### Added

- Add a cross-platform Tkinter desktop GUI (`epub2web-gui`) with a toolkit-independent worker controller, preview lifecycle controls, and PyInstaller worker-mode support.
- Add per-image, per-page, render, verification, and link-check progress reporting, with a determinate GUI progress bar and milestone log lines.
- Add `make gui-portable` and a release workflow that builds self-contained desktop artifacts: a single Windows `.exe`, a macOS `.dmg`, and a Linux AppImage or portable tarball, with packaged smoke tests, checksums, and third-party license notices.
- Add a tag-driven **Release** workflow that validates `vX.Y.Z` against the package version, builds the Python and portable artifacts, creates the GitHub release, and dispatches PyPI publishing.

### Changed

- Re-running a command for an existing epub2web site now refreshes it automatically instead of failing with an “output already exists” error. Unrelated folders are still refused.
- Refresh the desktop GUI with the reader's paper palette, custom typography, source/output cards, status indicator, metadata-aware title, custom build console scrollbar, and app icon.
- Generate GitHub release notes from the matching `CHANGELOG.md` section instead of GitHub's commit-derived notes.
- Disclose Windows SmartScreen and macOS Gatekeeper first-launch warnings, with platform-specific workarounds, in the README and portable packages.

### Fixed

- Preserve escaped source text that resembles markup, repair missing `#fnN`/`#ffnN` footnote anchors, and normalize malformed external links produced by print conversions.
- Report both fidelity and internal-link gate failures in the desktop GUI.

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
