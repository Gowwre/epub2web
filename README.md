# The Design of Everyday Things — browser edition

A complete, browser-optimized edition of Don Norman's 2013 revised and expanded text, built from the EPUB without rewriting the prose.

**Verified:** 118,977 source tokens match the built pages exactly — token-for-token and character-for-character. 40 figures, 71 notes, 159 references, and 1,081 index entries are all present. 3,826 internal links and assets resolve; no broken anchors, no duplicate ids.

---

## Quick start

```bash
# Python side
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Node side (Pagefind only)
npm install

# Build, index, and run the fidelity gate
npm run build

# Build + link check
npm run check

# Portable offline package (no hosting required)
npm run package:offline

# Preview at http://localhost:4321
npm run dev
```

Put the source EPUB in the project root. The extractor finds the first `*.epub`. The EPUB itself, the derived `content/`, and `dist/` are gitignored; the code and design assets are not.

To build for a real domain:

```bash
SITE_URL="https://your-domain.example" npm run build
```

Upload `dist/` to any static host. The site assumes it is served from the domain root.

## Distributing without hosting

`npm run package:offline` creates:

```
release/doet-browser-edition.zip          ~3.7 MB, no hosting
release/doet-browser-edition/             the unzipped package
```

The zip contains the complete site plus a tiny local-only server (`serve.py`) and one-click launchers:

- **macOS:** double-click `start.command`
- **Windows:** double-click `start.bat` (needs Python 3)
- **Linux:** run `start.sh`

The launcher opens `http://127.0.0.1:8000/` in the browser. It binds to `127.0.0.1` only, so the book is not exposed to the network and no internet connection is needed. Pagefind search, note previews, fonts, and images all work because the site is served properly rather than opened as `file://`.

You can email the zip, put it on a USB drive, or share it through any file-transfer service. The recipient needs Python 3; the README inside the package explains the options. If you need a true zero-install format (one self-contained HTML file that opens by double-click), that requires inlining the fonts/images and replacing the search index; the current package is the version that preserves all features.

The site and package are intentionally excluded from git. The text remains © Don Norman / Basic Books; see the rights note below.

---

## Why this pipeline

The hardest part of putting a book online is not the website. It is proving that the website still contains the book.

An LLM asked to "turn this EPUB into a website" will usually produce something plausible and quietly lossy: a dropped clause, a normalized quote, a merged paragraph, a caption rewritten as a summary. That is fine for a blog post. It is not fine for a book.

This project splits the work by what each tool is good at:

| Job | Tool | Why |
|---|---|---|
| Read the EPUB, map print classes to semantic HTML, group figures, rebuild notes, rewrite links | Python + BeautifulSoup | deterministic, repeatable, inspectable |
| Design the reading experience, write templates/CSS, iterate on typography and edge cases | LLM-assisted | cheap to review visually; no prose in the output path |
| Prove the prose is intact | `scripts/verify.py` | token + character comparison against the EPUB, fails the build |

The rule is simple: **the LLM may change the presentation, but it never authors the content.** If a transformation must touch text — for example, repairing a broken PDF extraction — it should return a patch, and the fidelity gate should decide whether the patch is acceptable.

---

## Pipeline

```
EPUB
  │
  ├─ scripts/extract.py       semantic fragments + source-text baseline
  │     ├─ content/pages/*.html
  │     ├─ content/book.json
  │     ├─ content/source-text.json
  │     └─ public/images/*.jpg|webp
  │
  ├─ templates/*.html         Jinja layouts
  ├─ static/assets/*          CSS, JS, self-hosted fonts
  │
  ├─ scripts/build.py         → dist/
  ├─ Pagefind                 → dist/pagefind/
  ├─ scripts/verify.py        token + character gate
  └─ scripts/check_links.py   internal links, anchors, images, ids
```

### What the extractor does

- Drops print-only artefacts: page anchors become invisible targets, running heads and spacer spans disappear, decorative drop caps are removed, hidden alternate images are skipped.
- Maps the EPUB's class soup (`bodytext`, `subheading4`, `hang`, `bulllist`, …) onto real HTML (`p`, `h2`, `h3`, `ul`, `ol`, `blockquote`, `figure`, `figcaption`, `table`).
- Groups consecutive images and captions into one `<figure>`, preserving multi-photo figures as a group.
- Rebuilds the endnote markers that the EPUB lost. Notes are keyed by the printed page number, so each superscript is a real link to the note and the note links back to its anchor.
- Rebuilds the printed TOC from the source TOC, including the back-matter entries.
- Rebuilds the index in source order, with indentation inferred from the source's lowercase subentries, plus a client-side filter and letter navigation.
- Rewrites every internal link to the new routes and preserves the printed page anchors so the index still works.
- Converts images to WebP with JPEG fallback, and writes width/height for every image.

The output is plain static HTML. There is no client-side rendering of the book text, no CMS, and no database.

### What the fidelity gate does

For every built page it takes the visible text inside `<main>`, removes generated chrome (`data-chrome`, `data-generated`), normalizes whitespace and Unicode, and compares it with the corresponding EPUB source files:

1. **Tokens** — exactly the same words, in exactly the same order.
2. **Characters** — after whitespace normalization, the normalized strings must be identical. This catches punctuation drift that a word-level check would miss.
3. **Counts** — notes, references, index entries, figures, cover image.
4. **Links** — every internal file, fragment, image, and `aria-describedby` target must exist; every page must have unique ids.

Run `npm run check` to see the report. A copy is written to `content/fidelity-report.json`.

---

## Design notes

- **Type:** Fraunces for display, Literata for reading, Inter for interface. Self-hosted, Latin + Latin Extended, variable fonts.
- **Reading column:** ~67 characters, fluid type, generous leading, `text-wrap: pretty`, old-style figures where appropriate.
- **Navigation:** sticky chapter/section sidebar on wide screens; full contents sheet on mobile; previous/next cards; arrow-key chapter navigation; reading progress.
- **Figures:** responsive groups, captions, keyboard-accessible lightbox.
- **Notes:** superscript page-number links with a hover/focus preview and a full notes page.
- **Index:** full 1,081-entry index with live filtering, letter navigation, and links back to the printed page anchors.
- **Search:** Pagefind, fully static, loaded only when the search dialog opens.
- **Theme:** light/dark via CSS custom properties, persisted locally.
- **Print:** a print stylesheet is included; the book still prints cleanly.
- **Accessibility:** semantic landmarks, skip link, visible focus states, `aria-current`, labelled controls, captions wired to figures, reduced-motion support.

---

## Source and rights

The text is © 2013 Don Norman, published by Basic Books. The EPUB used for this build was supplied locally by the user. **This browser edition is intended for personal reading; do not publish it without permission from the rights holder.** The code and design pipeline can be reused; the text cannot.

The source EPUB is intentionally not committed. `content/`, `dist/`, `public/images/`, and `node_modules/` are generated or local-only.

---

## Project layout

```
scripts/
  extract.py       EPUB → semantic fragments + source baseline
  build.py         fragments + templates → dist/
  verify.py        token/character fidelity gate
  check_links.py   internal link, anchor, image, duplicate-id check
templates/
  base.html        document shell, metadata, header/footer, dialogs
  page.html        reading page
  home.html        cover / landing page
  contents.html    full table of contents
  sidebar.html     chapter + section navigation
  dialogs.html     contents sheet, search, lightbox, note preview
  macros.html      inline SVG icons
static/assets/
  styles.css       the design system
  app.js           theme, menus, search, lightbox, notes, index filter
  fonts.css        self-hosted @font-face declarations
  fonts/           woff2 files
content/           generated; gitignored
dist/              generated; gitignored
release/           portable offline package; gitignored
```
