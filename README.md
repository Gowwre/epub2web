# epub2web

**Turn an EPUB into a website you can read and share in any browser.**

`epub2web` takes an ebook you already own and turns it into a clean,
comfortable website. It works on your computer, even offline. There is no
account, no upload, and no AI rewriting.

An EPUB is the standard ebook file format used by most ebook stores and reading
apps. This tool is for authors, translators, publishers, teachers, and readers
who want a readable web edition without handing the book to an online service.

[**Visit the website**](https://gowwre.github.io/epub2web/)
· [Download the desktop app](https://github.com/Gowwre/epub2web/releases/latest)
· [Try the live demo](https://gowwre.github.io/epub2web/demo/)

[![Latest release](https://img.shields.io/github/v/release/Gowwre/epub2web)](https://github.com/Gowwre/epub2web/releases)

![epub2web home page](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/home.png)

## Get the desktop app

The desktop app is the easiest way to use `epub2web`. It includes everything it
needs, so you do **not** need to install Python or any other software.

| Your computer | Download | How to start |
|---|---|---|
| Windows | `epub2web-gui-<version>-windows-x64.exe` | Double-click the file. |
| macOS, Apple Silicon | `epub2web-gui-<version>-macos-arm64.dmg` | Open the disk image, then drag the app to Applications. |
| macOS, Intel | `epub2web-gui-<version>-macos-x64.dmg` | Open the disk image, then drag the app to Applications. |
| Linux | `epub2web-gui-<version>-linux-x86_64.AppImage` | Make it executable, then run it. |

Most Macs sold since late 2020 use Apple Silicon. Choose the Intel download for
older Macs if you are unsure.

Download from the [latest release](https://github.com/Gowwre/epub2web/releases/latest).
Then:

1. Open the app.
2. Choose an EPUB file.
3. Click **Convert**.

The finished website opens in your browser. It is saved under
`Documents/epub2web/<book>-site` (or `~/epub2web/<book>-site` if you do not
have a Documents folder). The preview stays running while you read; use
**Stop** to shut it down. Closing the window also stops it. To read the site
again later, see [Run the site](#run-the-site).

The app shows live progress while it works, down to individual pages and
images, so a long book does not look frozen.

### First launch: security warnings are expected

The desktop builds do not have paid code-signing certificates yet. Windows and
macOS may show a security warning the first time you open the app. This is
expected, and it does not mean the download was tampered with — but only
continue if you downloaded it from the
[official releases page](https://github.com/Gowwre/epub2web/releases).

| Your computer | What you may see | What to do |
|---|---|---|
| Windows | “Windows protected your PC” | Click **More info**, then **Run anyway**. |
| macOS 15 (Sequoia) and later | Apple cannot verify the app | Try to open it, click **Done**, then use **System Settings → Privacy & Security → Security → Open Anyway**. |
| macOS 14 and earlier | Apple cannot verify the app | Right-click the app, choose **Open**, then click **Open** in the dialog. |
| Linux | Usually no warning | If the AppImage does not start, make it executable or try `--appimage-extract-and-run`. |

**Windows details**

1. Double-click the `.exe`.
2. If **Windows protected your PC** appears, click **More info**.
3. Click **Run anyway**.

If your PC is managed by a workplace or school, SmartScreen or Smart App
Control may block unsigned apps completely. Ask your administrator rather than
disabling security features. If Windows shows a “file came from another
computer” message, open the file's properties, select **Unblock**, and try
again. You can verify the download against the SHA-256 checksum on the release
page.

**macOS 15 and later details**

1. Open the `.dmg` and drag the app to **Applications**.
2. Try to open the app once. macOS blocks it.
3. Click **Done**.
4. Open **System Settings → Privacy & Security**.
5. Scroll down to **Security**, click **Open Anyway**, then authenticate.
6. Open the app again.

The **Open Anyway** button is available for about an hour after you try to open
the app. On macOS 15 and later, right-clicking the app and choosing **Open** no
longer bypasses this warning.

**macOS 14 and earlier details**

1. Open the `.dmg` and drag the app to **Applications**.
2. Right-click the app, choose **Open**, then click **Open** in the dialog.

**Advanced macOS workaround**

If you are comfortable with Terminal, you can remove the quarantine flag from
an app downloaded from the official release:

```bash
xattr -dr com.apple.quarantine /Applications/epub2web-gui.app
```

Adjust the path if the app is somewhere else. If macOS says the app is damaged,
delete it, re-download it, and try again before using this command.

See [docs/gui.md](https://github.com/Gowwre/epub2web/blob/main/docs/gui.md) for
more about portable builds and first-launch warnings.

## What you get

A complete website, ready to read — not a raw document dump:

- a cover page and a clickable table of contents
- every chapter as a clean, readable web page
- pictures, captions, tables, lists, notes, and cross-references
- built-in search that works without an account or internet connection
- light and dark reading modes
- a layout that works on phones, tablets, and desktops
- keyboard navigation, accessible labels, and image descriptions
- your text exactly as it appears in the EPUB

You can keep the site on your computer, or put it online with any web host.
The [technical section](#for-technical-users) lists hosting and subpath
options.

![epub2web reading view](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/reading.png)

![Built-in search](https://raw.githubusercontent.com/Gowwre/epub2web/main/docs/search.png)

## Your book stays your book

Most EPUB-to-website tools either look like a document dump or quietly rewrite
the text. `epub2web` follows one rule: **the EPUB is the source of truth**.

- **No AI. No rewriting.** The app does not call a language model or a remote
  service. The text you see is the text in your book, and the book is never sent
  to an AI service.
- **Checked word for word.** Every page is compared with its EPUB source. A
  dropped sentence, changed punctuation mark, or moved paragraph stops the
  build.
- **Images are checked too.** If a figure goes missing, the build fails instead
  of publishing a site with a hole in it.
- **Links are checked.** Internal links, anchors, images, and duplicate IDs are
  verified before the site is published.
- **Nothing is uploaded.** Your book and the generated site stay on your
  computer.

If a check fails, `epub2web` stops and leaves any previous working site
untouched. It does not publish a half-finished version.

## Where your files go

These paths apply to the desktop app:

- **Book website:** `Documents/epub2web/<book>-site`, or
  `~/epub2web/<book>-site` when there is no Documents folder.
- **Logs:** the platform application-data folder (`~/.local/share/epub2web` on
  Linux, `~/Library/Application Support/epub2web` on macOS, and
  `%LOCALAPPDATA%\epub2web` on Windows).
- **Failure reports:** a support ZIP, written to the reports folder under the
  same application-data directory.

Removing the app does not remove your books, generated sites, or logs.

## Run the site

The desktop app starts a small local web server and opens the finished site in
your browser. That preview lasts only while the app is open. **Stop** shuts the
server down, and closing the window does too.

To read the site later, either reopen the app and convert the same EPUB again
(the existing site is refreshed and the preview starts again), or serve the
folder yourself.

**Do not double-click `index.html`.** The generated site uses absolute links,
and its search index is loaded over HTTP. Browsers block those requests when a
page is opened directly from the filesystem.

From the site folder, run a static file server. Replace `my-book-site` with
the folder name shown by the app, and adjust the path if the site is somewhere
else. For example:

macOS or Linux:

```bash
cd ~/Documents/epub2web/my-book-site
python3 -m http.server 8000
```

Windows PowerShell:

```powershell
cd ~\Documents\epub2web\my-book-site
py -m http.server 8000
```

Then open <http://localhost:8000/> in your browser. Any static file server
works; Python is only one option. If you use the command line, the equivalent
build-and-serve command is:

```bash
epub2web book.epub --serve
```

To share the site, upload the same folder to a static host. See
[Hosting and subpaths](#hosting-and-subpaths).

## If a book does not convert

Some books contain markup or images that `epub2web` cannot safely convert. When
that happens, the app stops rather than dropping content.

It also creates one support ZIP and shows its path. Attach that ZIP to a
[bug report](https://github.com/Gowwre/epub2web/issues/new). Do not attach the
book itself: the ZIP is usually enough, and it may contain file paths, book
metadata, and short excerpts from failed comparisons. Review it before sharing.

You can also try the [command-line version](#for-technical-users) to see more
detail.

## For technical users

[![CI](https://github.com/Gowwre/epub2web/actions/workflows/ci.yml/badge.svg)](https://github.com/Gowwre/epub2web/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/Gowwre/epub2web/blob/main/LICENSE)

<details>
<summary><strong>Install with Python</strong></summary>

`epub2web` needs Python 3.10 or newer.

PyPI publishing is not configured yet, so install directly from GitHub for now:

```bash
pipx install git+https://github.com/Gowwre/epub2web
epub2web book.epub --serve
```

Or with [`uv`](https://docs.astral.sh/uv/):

```bash
uvx --from git+https://github.com/Gowwre/epub2web epub2web book.epub --serve
```

From a checkout:

```bash
pip install -e .
epub2web book.epub --serve
```

The desktop GUI also needs Tk. On Debian/Ubuntu:

```bash
sudo apt install python3-tk
```

Once PyPI publishing is enabled, `pip install epub2web` will work too. Track
that setup in [issue #1](https://github.com/Gowwre/epub2web/issues/1).

</details>

<details>
<summary><strong>Command-line usage and options</strong></summary>

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

The output is a plain folder:

```text
book-site/
  .epub2web            identifies the folder as an epub2web site
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

Because the site uses absolute paths and loads its search index when needed,
serve the folder rather than opening `index.html` directly from the filesystem.

</details>

<details>
<summary><strong>How the checks and failure handling work</strong></summary>

- The extractor maps print-oriented EPUB markup to semantic HTML, groups figures
  and captions, rewrites links, and repairs common EPUB layout artefacts.
- A **fidelity gate** compares every rendered page with its source,
  token-for-token and character-for-character. A dropped clause, changed
  punctuation mark, or moved paragraph fails the build.
- An **image gate** compares the number of images on each source page with the
  rendered page, so a missing figure cannot pass silently.
- A **link gate** checks every internal anchor, image, asset, and duplicate ID.
- The build never calls a language model or a remote service. The same EPUB
  always produces the same text and structure; only the sitemap's build
  timestamp changes.
- The site is built in a staging directory, verified, and only then swapped into
  place. If extraction or a gate fails, an existing site is left untouched.
- Re-running a command for a site that `epub2web` created refreshes it
  automatically. A non-empty folder that does not look like an epub2web site is
  refused instead of being overwritten. Sites built by earlier versions need
  `--force` once so the marker file can be added.
- `--force` refuses to replace the current directory, the home directory, any
  directory containing the input EPUB, or a non-empty directory that does not
  look like an epub2web site.
- Missing images, invalid images, and remote image references stop the build
  with the page and file named. Embedded base64 data-URI images are extracted
  into the site.
- Source scripts, event handlers, `javascript:` URLs, hidden source attributes,
  and other active content are removed before rendering. Metadata embedded in
  JSON-LD is escaped so it cannot break out of its script element.

</details>

<details>
<summary><strong>Logs and support reports</strong></summary>

Every command writes a run id, environment details, stage timings, and errors to
a persistent log. On failure the CLI also creates one support ZIP and prints its
path:

```text
error: ...
Report:  /home/you/project/epub2web-reports/epub2web-report-20261027-121019-12b49c2dd2.zip
         attach this file when reporting the problem
```

The support ZIP contains `README.txt`, the full human log, JSONL events, a
machine-readable summary, and any fidelity/link reports.

Each run produces:

- `epub2web-*.log` — human-readable stages, warnings, gate failures, traceback
- `epub2web-*.jsonl` — the same events as structured JSON lines
- `epub2web-*-fidelity.json` — the complete text/image gate result, when that gate runs
- `epub2web-*-links.json` — the complete link/anchor report, when that gate runs
- `epub2web-*-summary.json` — machine-readable run summary

Logging never makes a build fail: if the log directory is not writable, the
command warns once and continues. The default directory keeps the latest 20
runs; set `EPUB2WEB_LOG_DIR` to change it.

Logs and support ZIPs can contain file paths, book metadata, and short excerpts
from failed comparisons. Review them before attaching them to a public issue.

</details>

<details>
<summary><strong>Hosting and subpaths</strong></summary>

The generated site is a plain folder of files. Host it on any static service —
GitHub Pages, Cloudflare Pages, Netlify, S3, nginx — or serve it locally with
`epub2web book.epub --serve`.

Project sites such as GitHub Pages serve from a subpath
(`https://username.github.io/epub2web/`). Build with `--base-path` so every
link, stylesheet, font, and search request points at that prefix:

```bash
epub2web book.epub -o site \
  --base-path /epub2web \
  --site-url https://username.github.io
```

`--base-path` also affects the sitemap, canonical URLs, and the built-in
search. `--serve` previews the site at the same subpath:

```bash
epub2web book.epub --base-path /epub2web --serve
# http://127.0.0.1:8000/epub2web/
```

The included [demo workflow](https://github.com/Gowwre/epub2web/blob/main/.github/workflows/pages.yml)
builds the landing page at the project root and this demo under `/demo/` on
GitHub Pages.

</details>

<details>
<summary><strong>Development</strong></summary>

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
make demo EPUB=book.epub
make gui-portable # self-contained desktop GUI for this OS
make release-notes VERSION=0.1.0
make release-prepare VERSION=0.4.0
make release-ship VERSION=0.4.0
make clean
```

The test fixture is generated in `tests/conftest.py`; no copyrighted book is
required. Maintainers should read [RELEASING.md](https://github.com/Gowwre/epub2web/blob/main/RELEASING.md)
for the tag-driven release and PyPI setup.

</details>

## Limitations

- Works best with normal, reflowable EPUB 2/3 books. Fixed-layout, image-only,
  and DRM-protected EPUBs may not work.
- Books that load images from the internet are refused so the generated site
  stays self-contained. Embed the images in the EPUB first.
- Inline SVG is stripped for safety; external SVG images are sanitized and kept.
  Images referenced only from CSS backgrounds are not converted.
- Audio, video, forms, and interactive widgets are not converted.
- Unusual print-conversion markup may need a small converter rule. The fidelity
  gate stops a lossy conversion instead of guessing.
- A spine document containing several chapters becomes one reading page.
- A single-file HTML mode is not available yet; the output is a static site
  folder.
- PDF input is out of scope.

If a book fails, open an issue with the command, the failing page, and a minimal
markup sample (no copyrighted text). See [CONTRIBUTING.md](https://github.com/Gowwre/epub2web/blob/main/CONTRIBUTING.md).

## License and rights

The code and theme are **MIT** licensed. Your EPUB and generated site remain
yours; `epub2web` does not include or redistribute book text.

The self-hosted fonts are under the SIL Open Font License; see
[THIRD_PARTY_NOTICES.md](https://github.com/Gowwre/epub2web/blob/main/THIRD_PARTY_NOTICES.md).
Only publish books you have the right to publish.
