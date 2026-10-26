# epub2web

**Turn an EPUB into a beautiful, browser-optimized website — deterministically.**

[Try the live demo](https://gowwre.github.io/epub2web/) — a public-domain edition of *Alice's Adventures in Wonderland*.

No AI at runtime. No prose rewriting. No Node, bundler, or database. Just Python, static HTML, and a fidelity gate that refuses to lose a word.

[![CI](https://github.com/Gowwre/epub2web/actions/workflows/ci.yml/badge.svg)](https://github.com/Gowwre/epub2web/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

![epub2web home page](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/home.png)

## Quick start

The easiest way is [`uv`](https://docs.astral.sh/uv/). Install from GitHub:

```bash
uvx --from git+https://github.com/Gowwre/epub2web epub2web book.epub --serve
```

That builds `./book-site/`, starts a local server on `127.0.0.1`, and opens your browser. Press `Ctrl+C` to stop.

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

## What you get

A complete static site with:

- cover page, table of contents, chapter pages, and section anchors
- figures and captions, tables, lists, notes, and cross-references
- built-in full-text search, with no external service or PHP/Node runtime
- light and dark themes, reading progress, keyboard navigation
- responsive typography, print styles, and a mobile contents sheet
- semantic HTML, accessible labels, and image descriptions
- every page checked against the EPUB source before the command succeeds

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
- A **link gate** checks every internal anchor, image, and duplicate ID.
- The build never calls a language model or a remote service. The same EPUB always produces the same text and structure; only the sitemap's build timestamp changes.

That makes the tool useful for authors, translators, publishers, and anyone who wants a readable web edition without turning the text into training data.

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
| `--force` | Replace an existing output directory |
| `--keep-work` | Keep the intermediate extraction directory |
| `--version` | Print the version |

A run looks like this:

```text
EPUB:    Alice's Adventures in Wonderland
Author:  Lewis Carroll
Pages:   13
Words:   29,564
Site:    /home/you/alice-site/index.html
Verify:  PASS (13/13 pages exact)
Links:   PASS (625 checked, 0 broken, 0 duplicate ids)
Search:  16 sections indexed
Time:    0.54s
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

The included [demo workflow](.github/workflows/pages.yml) does exactly this
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

Maintainers: see [RELEASING.md](RELEASING.md) for the PyPI Trusted Publishing setup.

## Limitations

- **Reflowable EPUB 2/3** is the target. Fixed-layout, image-only, and DRM-protected EPUBs need additional work.
- Unusual print-conversion markup may need a small converter rule. The fidelity gate will stop a lossy conversion rather than let it pass.
- A single-file HTML mode is on the roadmap. Today the output is a static site folder, which is better for navigation, search, and images.
- PDF input is out of scope.

If a book fails, open an issue with the command, the failing page, and a minimal markup sample (no copyrighted text). See [CONTRIBUTING.md](CONTRIBUTING.md).

## License and rights

The code and theme are **MIT** licensed. Your EPUB and generated site remain yours; `epub2web` does not include or redistribute book text.

The self-hosted fonts are under the SIL Open Font License; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Only publish books you have the right to publish.
