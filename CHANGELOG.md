# Changelog

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
