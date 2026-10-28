# epub2web

**Turn an EPUB into a beautiful, browser-optimized website — deterministically.**

[Try the live demo](https://gowwre.github.io/epub2web/) — a public-domain edition of *Alice's Adventures in Wonderland*.

No AI at runtime. No prose rewriting. No Node, bundler, or database. Just Python, static HTML, and a fidelity gate that refuses to lose a word.

[![CI](https://github.com/Gowwre/epub2web/actions/workflows/ci.yml/badge.svg)](https://github.com/Gowwre/epub2web/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Gowwre/epub2web/blob/main/LICENSE)

![epub2web home page](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/home.png)

## Quick start

The easiest way is [`uv`](https://docs.astral.sh/uv/). Install from GitHub:

```bash
uvx --from git+https://github.com/Gowwre/epub2web epub2web book.epub --serve
```

That builds `./book-site/`, starts a local server on `127.0.0.1`, and opens your browser. Press `Ctrl+C` to stop. Run the same command again to refresh the site and reopen the preview; no `--force` is needed.

Once the package is published on PyPI, the shorter form works too:

```bash
uvx epub2web book.epub --serve
```

Prefer a permanent install? Use [`pipx`](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/Gowwre/epub2web
epub2web book.epub --serve
```

Or use plain pip (PyPI release):

```bash
pip install epub2web
epub2web book.epub -o my-site
```

From a checkout:

```bash
pip install -e .
epub2web book.epub --serve
```

Python 3.10+ is the only requirement.

## Desktop GUI

A small cross-platform Tkinter GUI is included:

```bash
pip install -e .
epub2web-gui
```

Choose an EPUB, click **Convert**, and the finished site opens in your default
browser. The site is built under `~/Documents/epub2web/<book>-site` (or
`~/epub2web/<book>-site` if there is no `Documents` folder). The preview server
stays running while you read; use **Stop** to shut it down. Closing the window
also stops it.

The build log and progress bar update continuously — down to individual images
and pages — so a long book does not look stalled.

On Linux, install Tk first if your distribution does not include it:

```bash
sudo apt install python3-tk
```

See [docs/gui.md](https://github.com/Gowwre/epub2web/blob/main/docs/gui.md) for the
architecture and PyInstaller packaging instructions.

## What you get

A complete static site with:

- cover page, table of contents, chapter pages, and section anchors
- figures and captions, tables, lists, notes, and cross-references
- built-in full-text search, with no external service or PHP/Node runtime
- light and dark themes, reading progress, keyboard navigation
- responsive typography, print styles, and a mobile contents sheet
- semantic HTML, accessible labels, and image descriptions
- every page and every rendered image checked against the EPUB source before the command succeeds

![epub2web reading view](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/reading.png)

The output is a plain folder:

```
book-site/
  index.html
  contents/index.html
  read/1/index.html
  read/2/index.html
  assets/              CSS, JS, self-hosted fonts
  images/              optimized figures
  search-index.json
  sitemap.xml
  robots.txt
```

Host it on any static service — GitHub Pages, Cloudflare Pages, Netlify, S3, nginx — or serve it locally with `epub2web book.epub --serve`.

## Why it is different

Most “EPUB to website” tools either look like a document dump or quietly rewrite the book. `epub2web` is built around one rule: **the EPUB is the source of truth**.

- The extractor maps print-oriented markup to semantic HTML, groups figures and captions, rewrites links, and repairs common EPUB layout artefacts.
- A **fidelity gate** compares every rendered page with its source, token-for-token and character-for-character. A dropped clause, changed punctuation mark, or moved paragraph fails the build.
- An **image gate** compares the number of images on each source page with the rendered page, so a missing figure cannot pass silently.
- A **link gate** checks every internal anchor, image, asset, and duplicate ID.
- The build never calls a language model or a remote service. The same EPUB always produces the same text and structure; only the sitemap's build timestamp changes.

That makes the tool useful for authors, translators, publishers, and anyone who wants a readable web edition without turning the text into training data.

## Failure handling and safety

A failed build is not allowed to damage a working site.

- The site is built in a staging directory, verified, and only then swapped into place. If extraction or a gate fails, an existing site is left untouched and no half-built output is published.
- Re-running a command for a site that epub2web created refreshes that site automatically. A non-empty folder that does not look like an epub2web site is refused instead of being overwritten.
- `--force` refuses to replace the current directory, the home directory, any directory containing the input EPUB, or a non-empty directory that does not look like an epub2web site.
- Missing images, invalid images, and remote image references stop the build with the page and file named. Embedded base64 data-URI images are extracted into the site.
- An EPUB with no readable spine pages fails instead of producing an empty website.
- Source scripts, event handlers, `javascript:` URLs, hidden source attributes, and other active content are removed before rendering. Metadata embedded in JSON-LD is escaped so it cannot break out of its script element.
- `--keep-work` preserves the failed site and the extraction report for inspection; otherwise temporary directories are removed.

That makes failure modes explicit: the tool stops rather than silently dropping a figure, a page, or a scriptable payload.

## Diagnostics and logs

Every command writes a run id, environment details, stage timings, and errors to a persistent log. On failure the CLI also creates one support ZIP and prints its path prominently:

```text
error: ...
Report:  /home/you/project/epub2web-reports/epub2web-report-20261027-121019-12b49c2dd2.zip
         attach this file when reporting the problem
```

The support ZIP contains `README.txt`, the full human log, JSONL events, a machine-readable summary, and any fidelity/link reports. End users only need to send that one file. Use `--report-dir` or `EPUB2WEB_REPORT_DIR` to choose where it is written; the default is `./epub2web-reports/` in the directory where the command ran.

Use `--log-dir` or `--log-file` to choose where the individual logs live. Each run produces:

- `epub2web-*.log` — human-readable stages, warnings, gate failures, traceback
- `epub2web-*.jsonl` — the same events as structured JSON lines
- `epub2web-*-fidelity.json` — the complete text/image gate result, when that gate runs
- `epub2web-*-links.json` — the complete link/anchor report, when that gate runs
- `epub2web-*-summary.json` — machine-readable run summary

Logging never makes a build fail: if the log directory is not writable, the command warns once and continues. The default directory keeps the latest 20 runs; set `EPUB2WEB_LOG_DIR` to change it.

Logs and support ZIPs are local diagnostics. They can contain file paths, book metadata, and short excerpts from failed comparisons, so review them before attaching to a public issue. The support ZIP includes a README with the same warning and instructions.

## CLI

```bash
epub2web book.epub --serve
epub2web book.epub -o my-site
epub2web book.epub -o my-site --site-url https://example.com
```

| Option | Meaning |
|---|---|
| `-o, --output DIR` | Output directory (default: `./<book-slug>-site`) |
| `--serve` | Build, then serve locally and open a browser |
| `--port N` | Preview port (default: `8000`) |
| `--no-browser` | Do not open a browser with `--serve` |
| `--title TEXT` | Override the book title |
| `--author TEXT` | Override the author |
| `--site-url URL` | Absolute URL used in metadata and the sitemap |
| `--base-path PATH` | Build for a subpath, e.g. `/epub2web` (default: site root) |
| `--no-verify` | Skip the text-fidelity gate (development only) |
| `--no-links` | Skip the internal-link gate (development only) |
| `--force` | Force replacement; reruns refresh an epub2web site automatically |
| `--keep-work` | Keep extraction files and a failed site for inspection |
| `--log-dir DIR` | Directory for run diagnostics (default: `~/.epub2web/logs`) |
| `--log-file FILE` | Write this run's human-readable log to an exact file |
| `--report-dir DIR` | Directory for failure support ZIPs (default: `./epub2web-reports`) |
| `--version` | Print the version |

A run looks like this:

```text
EPUB:    Alice's Adventures in Wonderland
Author:  Lewis Carroll
Pages:   13
Words:   29,564
Verify:  PASS (13/13 pages exact)
Links:   PASS (743 checked, 0 broken, 0 duplicate ids)
Search:  16 sections indexed
Site:    /home/you/alice-site/index.html
Time:    0.57s
Preview: epub2web alice.epub --serve
```

## Search

Search is built in. `epub2web` writes `search-index.json` and loads it only when the reader opens search. There is no Pagefind, Node, or third-party script.

Because the site uses absolute paths and fetches the index, serve the folder rather than opening `index.html` directly from the filesystem:

```bash
epub2web book.epub --serve
```

Any static web server works too.

![Built-in search](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/search.png)

## Hosting under a subpath

Project sites such as GitHub Pages serve from a subpath
(`https://username.github.io/epub2web/`). Build with `--base-path` so every
link, stylesheet, font, and search request points at that prefix:

```bash
epub2web book.epub -o site \
  --base-path /epub2web \
  --site-url https://username.github.io
```

`--base-path` also affects the sitemap, canonical URLs, and the built-in
search. `--serve` previews the site at the same subpath, so you can check the
deployed URLs locally:

```bash
epub2web book.epub --base-path /epub2web --serve
# http://127.0.0.1:8000/epub2web/
```

The included [demo workflow](https://github.com/Gowwre/epub2web/blob/main/.github/workflows/pages.yml) does exactly this
for the project's public-domain Alice in Wonderland demo.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
make test
```

`make test` runs Ruff and pytest against a generated tiny EPUB. Other targets:

```bash
make lint
make format
make build        # sdist + wheel
make check-dist   # twine check
make clean
```

The test fixture is generated in `tests/conftest.py`; no copyrighted book is required.

Maintainers: see [RELEASING.md](https://github.com/Gowwre/epub2web/blob/main/RELEASING.md) for the PyPI Trusted Publishing setup.

## Limitations

- **Reflowable EPUB 2/3** is the target. Fixed-layout, image-only, and DRM-protected EPUBs need additional work.
- Remote image URLs are rejected because the generated site must stay self-contained and should not leak reader requests. Download and embed those images in the EPUB first.
- Inline SVG is stripped for safety; external SVG images are sanitized and kept. Images referenced only from CSS backgrounds are not converted. Use raster `<img>`/`<figure>` markup for figures that must appear in the browser.
- Audio, video, forms, and interactive widgets are not converted; their fallback text is omitted.
- Unusual print-conversion markup may need a small converter rule. The fidelity gate will stop a lossy conversion rather than let it pass.
- A spine document that contains several chapters becomes one reading page. Splitting at TOC boundaries is a future improvement.
- A single-file HTML mode is on the roadmap. Today the output is a static site folder, which is better for navigation, search, and images.
- PDF input is out of scope.

If a book fails, open an issue with the command, the failing page, and a minimal markup sample (no copyrighted text). See [CONTRIBUTING.md](https://github.com/Gowwre/epub2web/blob/main/CONTRIBUTING.md).

## License and rights

The code and theme are **MIT** licensed. Your EPUB and generated site remain yours; `epub2web` does not include or redistribute book text.

The self-hosted fonts are under the SIL Open Font License; see [THIRD_PARTY_NOTICES.md](https://github.com/Gowwre/epub2web/blob/main/THIRD_PARTY_NOTICES.md). Only publish books you have the right to publish.
