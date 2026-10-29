# Fonts and writing systems

The reader theme self-hosts every font it uses. A generated site never requests
a font from a remote service.

## Bundled families

- **Literata** — body text for Latin, Greek, and Cyrillic scripts.
- **Fraunces** — display headings for Latin text.
- **Inter** — interface text for Latin, Greek, and Cyrillic scripts.
- **Noto Naskh Arabic** and **Noto Sans Arabic** — Arabic body and interface text.
- **Noto Serif Hebrew** and **Noto Sans Hebrew** — Hebrew body and interface text.
- **Noto Serif Devanagari** and **Noto Sans Devanagari** — Devanagari body and interface text.
- **Noto Serif Thai** and **Noto Sans Thai** — Thai body and interface text.
- **Noto Serif SC / TC / JP / KR** — CJK body, display, and interface text. The
  regional family is selected from the book language and the characters
  present in the book.

All families are licensed under the SIL Open Font License 1.1. See
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Per-book selection

`epub2web/fonts.py` scans the extracted text for script ranges. During rendering,
`epub2web/render.py` selects only the subsets needed by that book, copies their
WOFF2 files into `assets/fonts/`, and generates `assets/fonts.css` with
matching `@font-face` and `unicode-range` rules. Latin is always included.

The CJK selection uses kana for Japanese, Hangul for Korean, and the book
language for Chinese variants (`zh-Hans`/`zh-CN` → SC,
`zh-Hant`/`zh-TW`/`zh-HK` → TC). A mixed-script book can include more than one
regional family. If the language is ambiguous, Simplified Chinese is the
fallback.

Font files are never downloaded while building a book. The vendored files and
`font-manifest.json` are maintained with:

```bash
python3 scripts/fetch_fonts.py
```

That command needs network access and should only be run when intentionally
updating the bundled font set. It rewrites the manifest and the WOFF2 files.
