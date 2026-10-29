# Changelog

All notable, user-facing changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## Unreleased

### Added

- Add reading settings for text size and line spacing, remembered locally in the browser.
- Make the mobile contents sheet compact by collapsing chapter sections on demand, highlighting the current chapter, and opening scrolled to it.
- Add arrow-key and Enter navigation for search results.
- Add self-hosted font subsets for Greek, Cyrillic, Arabic, Hebrew, Devanagari, Thai, and CJK, with only the scripts present in a book copied into its site.
- Add right-to-left layout support for RTL book languages, including logical positioning and mirrored navigation arrows.
- Count CJK and Thai reading length by characters for estimates and whole-book progress.

## 0.5.0 - 2026-10-29

### Added

- Add a **Change…** action next to the desktop app’s output path so you can choose where generated sites are saved. The app creates the `<book>-site` folder inside the selected location.
- Remember the reader’s place and show progress through the whole book, with a **Continue reading** action on the home page and a **Start over** option. Positions are stored locally in the browser per EPUB file; rebuilding the same EPUB preserves them, while a different EPUB starts a separate position.

### Changed

- Use a stable local preview port in the desktop app so the browser can keep the reading position between runs.

### Fixed

- Show paths that sit directly in the home folder correctly in the desktop app instead of adding a stray `~.` prefix.

## 0.4.0 - 2026-10-29

### Added

- Add GitHub and project website shortcuts to the desktop GUI header.
- Check GitHub Releases at desktop GUI startup and show an **Update** button when a newer version is available. The button opens release notes and a download-page link. The check runs in the background, fails silently offline, and can be disabled with `EPUB2WEB_NO_UPDATE_CHECK=1`.

### Changed

- Point the download page’s Release notes button at the site changelog instead of the GitHub release page.

## 0.3.0 - 2026-10-28

### Added

- Add a public Astro landing site and download page, with a first-launch FAQ for Windows SmartScreen and macOS Gatekeeper warnings. The Pages workflow publishes the landing page at the project root and moves the live demo to `/demo/`.
- Add a dedicated changelog page with a GitHub link for every published release.
- Add a “Run the site” guide to the README and landing page covering the desktop preview, reopening a site, local static-server commands, and why `index.html` cannot be opened directly.
- Mark generated sites with an `.epub2web` file and a generator meta tag so refreshes cannot replace unrelated folders by accident.

### Changed

- Download buttons now point directly at the current release’s Windows, macOS, and Linux files instead of the GitHub release page. The Pages build resolves the latest assets, and a new release refreshes the download page automatically.
- Detect the visitor’s platform on the download page, recommend and highlight the matching installer, and fall back to a neutral platform picker on phones, ChromeOS, ARM Linux, unknown agents, or without JavaScript.
- Remove the non-functional note-preview and index-filter UI assets from the reading theme.

### Fixed

- Prevent narrow mobile layouts from clipping the homepage hero, header, release output, and long code snippets.
- Show each reading page’s estimated reading time instead of an empty chapter-meta line.
- Reject internal links whose `..` segments escape the generated site, and require root-relative links to include the configured base path.
- Preserve valid EPUB source IDs that previously collided with template IDs such as `main` or `top`.
- Split title overrides containing colons or dashes consistently, and read years from non-ISO publication dates instead of showing a truncated month.
- Keep the support ZIP when one JSONL event line is malformed.
- Resolve relative GUI log and report paths against the worker’s working directory.

### Security

- Harden external SVG sanitization by removing SMIL animation elements and `javascript:`, `file:`, and `data:` attribute values.

### Upgrade notes

- Sites built before this release do not have the `.epub2web` marker. Refreshing one without `--force` is refused; pass `--force` once to migrate it and add the marker.

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
