# Highlights and notes: storage, persistence, and migration

This document is research and design, not an implemented feature. It answers
three questions:

1. How should highlights and notes be stored?
2. How can they survive regenerating the site?
3. How can existing calibre highlights and notes be migrated?

The short version:

- Store annotations **outside the generated site**, in the browser (and
  optionally in the desktop app's data directory). Never put private notes into
  a site that may be published.
- Key the store by a **book content identity**, not by the output path, page
  route, or EPUB file hash alone. Keep the existing file hash as an alias.
- Anchor a highlight with **several selectors**, not one: a DOM range, an EPUB
  source locator (CFI or normalized source offset), and a text quote with
  surrounding context. Resolve the cheapest selector first and fall back.
- Migrate calibre annotations by reading its JSON exports/database, using the
  calibre CFI as a hint and `highlighted_text` as verification. Merge by
  calibre's identity rules (UUID for highlights, title for bookmarks), honor
  `removed` tombstones, and report unresolved items instead of dropping them.
- Calibre is the first adapter, not the whole feature. Other readers need their
  own storage parser and locator converter; the shared import, matching, merge,
  and review pipeline is what makes each additional reader cheaper.

## 1. What the reader does today

`epub2web` has no annotation layer. It stores only reading progress and display
settings in `localStorage`:

- `epub2web:progress:v1:<reading_id>` stores the last page key and scroll ratio.
- `epub2web-reader:v1` stores type size, spacing, width, and paragraph style.
- `epub2web-theme` stores the color theme.

`reading_id` is `sha256(EPUB file bytes)` (`epub2web/generic.py`). The renderer
also gives each page a `key` derived from its source file list
(`epub2web/render.py`), and routes are positional (`/read/1/`, `/read/2/`, …).

That design has two consequences for annotations:

- Browser storage is scoped to the **origin** (scheme, host, and port), not to
  the output directory. Rebuilding into the same address keeps browser data;
  moving to a different port, host, or `file://` starts a separate store.
- Any change to the EPUB bytes changes `reading_id`, even if the text is
  identical. Re-saving, re-zipping, or letting calibre write annotations into
  the EPUB changes the hash. Page keys are only a hash of the source-file list;
  two pages split from the same EPUB file can share a key, so a page key is not
  a precise text anchor either.

Annotations need a more forgiving identity than reading progress currently has.

## 2. How calibre stores annotations

Calibre has several durable-ish locations and two exchange formats. They are
related but not interchangeable.

### 2.1 The library database (authoritative for library books)

For a book in a calibre library, annotations live in the library's
`metadata.db` in the `annotations` table:

| Column | Meaning |
|---|---|
| `book` | Calibre book id |
| `format` | `EPUB`, `AZW3`, etc. |
| `user_type` | Usually `local`; `web` for a content-server user |
| `user` | Usually `viewer`; a content-server user name otherwise |
| `timestamp` | Seconds since the epoch |
| `annot_id` | Bookmark title, or highlight UUID |
| `annot_type` | `bookmark` or `highlight` |
| `annot_data` | The annotation object as JSON |
| `searchable_text` | Normalized text used by the FTS index |

The unique key is `(book, user_type, user, format, annot_type, annot_id)`.
Calibre builds two FTS5 indexes over `searchable_text`; for highlights that text
is `highlighted_text` plus `notes`, separated by `\x1f`.

Last-read positions are **not** in that table. They live in
`last_read_positions` with a separate CFI and progress fraction.

Relevant calibre source:
[`resources/metadata_sqlite.sql`](https://github.com/kovidgoyal/calibre/blob/master/resources/metadata_sqlite.sql),
[`src/calibre/db/annotations.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/annotations.py),
and [`src/calibre/db/backend.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/backend.py).

### 2.2 The viewer's per-book JSON cache

The viewer also writes a plain JSON array to the calibre configuration
directory:

```text
<calibre config dir>/viewer/annots/<sha256(absolute book path)>.json
```

The configuration directory is platform-specific:

| Platform | Calibre configuration directory |
|---|---|
| Linux | `$CALIBRE_CONFIG_DIRECTORY`, otherwise `$XDG_CONFIG_HOME/calibre` or `~/.config/calibre` |
| macOS | `$CALIBRE_CONFIG_DIRECTORY`, otherwise `~/Library/Preferences/calibre` |
| Windows | `$CALIBRE_CONFIG_DIRECTORY`, otherwise `%APPDATA%\calibre` |

`CALIBRE_CONFIG_DIRECTORY` overrides the platform default on every system, and
portable calibre installations set it explicitly. The key is `sha256` of the
absolute path to the book, so moving or renaming the file loses this cache. It
is a cache/fallback, not a portable identity.

### 2.3 The optional in-EPUB copy

If the viewer preference "Keep a copy of annotations/bookmarks in the e-book
file" is enabled, calibre writes:

```text
META-INF/calibre_bookmarks.txt
```

The file starts with this exact line:

```text
encoding=json+base64:
```

The remainder is the base64 encoding of a JSON array of annotation objects,
wrapped at 80 characters per line. Calibre can read this file when loading a
book, and merges it with the other copies. Writing it modifies the EPUB, which
changes the file hash.

Source:
[`src/calibre/gui2/viewer/annotations.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/gui2/viewer/annotations.py)
and `EPUB_FILE_TYPE_MAGIC` in
[`src/calibre/srv/render_book.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/srv/render_book.py).

### 2.4 The OPF copy

When calibre writes a `metadata.opf` (for example while exporting or backing up
a library), it can include annotations as repeated metadata elements:

```xml
<meta name="calibre:annotation" content="{...annotation JSON...}"/>
```

This is a copy made during metadata serialization, not the live database. It is
useful for migrating an exported library folder that has no `metadata.db`.

Source:
[`src/calibre/ebooks/metadata/opf2.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/ebooks/metadata/opf2.py).

### 2.5 Export formats

There are two JSON shapes in current calibre:

- **Viewer export** (`Export` in `gui2/viewer/highlights.py`):

  ```json
  {
    "version": 1,
    "type": "calibre_highlights",
    "highlights": [ ... ]
  }
  ```

- **Annotation collection** (the `calibredb annotations export` command and
  the Browse annotations tool):

  ```json
  {
    "version": 1,
    "type": "calibre_annotation_collection",
    "annotations": [
      { "book_id": 42, "format": "EPUB", "user_type": "local", "user": "viewer", ... }
    ]
  }
  ```

The collection format is the better automation target: it carries the book,
format, and user, and recent calibre versions can import it with
`calibredb annotations import BOOK_ID EPUB FILE`. The viewer's
`calibre_highlights` export is one-way in the viewer itself.

Calibre's import rules are the model to copy:

- highlights are matched by `uuid`;
- bookmarks are matched by `title`;
- the newer `timestamp` wins;
- deleted annotations remain as `removed: true` tombstones for merging;
- only known text fields are imported, so a collection cannot overwrite
  arbitrary metadata.

### 2.6 The annotation object

A calibre highlight looks like this (values shortened; the field shapes are
from calibre's source and the Foliate interoperability discussion):

```json
{
  "type": "highlight",
  "uuid": "2f0c...",
  "timestamp": "2026-01-14T16:32:01.028972+00:00",
  "highlighted_text": "the selected text",
  "notes": "a private note",
  "style": { "kind": "color", "which": "yellow", "type": "builtin" },
  "spine_index": 37,
  "spine_name": "epub/text/chapter-32.xhtml",
  "start_cfi": "/2/4/2[chapter-32]/34/1:7",
  "end_cfi": "/2/4/2[chapter-32]/34/1:91",
  "toc_family_titles": ["Chapter 32", "Cetology"]
}
```

A bookmark looks like this:

```json
{
  "type": "bookmark",
  "title": "A bookmark",
  "timestamp": "2026-01-14T16:32:01.028972+00:00",
  "pos_type": "epubcfi",
  "pos": "epubcfi(/6/2!/4/2)"
}
```

Notes are not a separate type. A note is the `notes` field on a highlight.
Calibre's "add note" flow creates a highlight (possibly with an empty quote)
and attaches the note to it.

Key details:

- `start_cfi` and `end_cfi` on a highlight are **relative to the spine item**;
  they do not include the `epubcfi(...)` wrapper. To make a full CFI, calibre
  prefixes `2 * (spine_index + 1)`, e.g. spine index 0 → `/2`, index 37 → `/76`.
- `spine_index` is zero-based. `spine_name` is the manifest href and is more
  stable than the index if the spine is reordered.
- Bookmarks and last-read positions use a full `epubcfi(...)` in `pos`.
- Calibre's CFI is not fully standard: it includes an extra root step and can
  produce incorrect offsets. Do not treat a CFI as authoritative without the
  quote. See the [Foliate interoperability issue](https://github.com/johnfactotum/foliate/issues/849).
- `style` is either a built-in color (`yellow`, `green`, `blue`, `red`,
  `purple`), a built-in decoration (`wavy`, `strikeout`), or a custom style
  dictionary.
- `toc_family_titles` is for grouping in exports; it is not an anchor.
- `removed` is a tombstone. Deleted highlights may keep only the skeleton
  fields (type, uuid, timestamp, removed).

### 2.7 What calibre does not solve

- It has no portable book identity across editions. The viewer sidecar is keyed
  by absolute path, and the library database is keyed by calibre book id.
- It has no general standard for annotation interchange. The calibre JSON
  collection is the closest thing to a usable interchange format.
- It does not make CFIs reliable enough to be the only anchor.
- It does not solve cross-device sync without a library or content server.

## 3. What to copy and what not to copy

Worth copying:

- multiple selectors per annotation;
- stable UUID identity and tombstones for merge;
- newest-timestamp-wins merging;
- a plain, versioned JSON export;
- a style vocabulary that maps cleanly to CSS;
- a migration report that distinguishes imported, unchanged, and unresolved.

Not worth copying:

- a single JSON object keyed by an absolute path;
- the normalized library database schema;
- CFI as the only location;
- annotations embedded in the published output;
- copying calibre's implementation instead of writing against the format. Code
  reuse is license-compatible now that this project is GPL-3.0-or-later, but
  preserve notices and prefer a small, testable implementation.

## 4. Recommended data model

### 4.1 Book identity

Use two identities and keep aliases:

- `source_sha256`: the existing `reading_id`, a hash of the EPUB bytes. Exact,
  cheap, and useful for "same file".
- `content_id`: a hash of the normalized text of the EPUB spine, in spine order.
  This survives re-zipping and metadata-only changes, and is the primary key for
  annotations.

The content hash should be computed from the **source EPUB text**, not from the
rendered site, so converter changes do not invalidate annotations:

```python
h = hashlib.sha256()
for item in epub.spine:
    body = source_body(item.path)
    h.update(normalize_text(text_of(body)).encode("utf-8"))
    h.update(b"\0")
content_id = h.hexdigest()
```

Add ISBN, title, author, and language as matching hints, not as primary keys.
Store all known identities as aliases:

```json
{
  "book": {
    "content_id": "…",
    "source_sha256": "…",
    "title": "…",
    "author": "…",
    "isbn": "…",
    "aliases": [
      { "scheme": "epub-sha256", "value": "…" },
      { "scheme": "isbn", "value": "…" }
    ]
  }
}
```

Lookup order when opening a book:

1. `content_id` exact match;
2. any `source_sha256` alias;
3. ISBN exact match;
4. normalized title + author, only with user confirmation;
5. otherwise offer import.

Never silently attach a store from a different edition to a book just because
the title matches.

### 4.2 Annotation document

One JSON document per book, with per-annotation records and tombstones:

```json
{
  "schema": "epub2web.annotations",
  "version": 1,
  "book": {
    "content_id": "…",
    "source_sha256": "…",
    "title": "…",
    "author": "…",
    "isbn": "…",
    "aliases": []
  },
  "annotations": [
    {
      "id": "8f14e45f-ea0b-4c7b-9c2f-2f6d6c7a1b3e",
      "type": "highlight",
      "created": "2026-11-04T10:00:00.000Z",
      "updated": "2026-11-04T10:00:00.000Z",
      "deleted": false,
      "note": "private note text",
      "quote": "the selected text",
      "style": { "color": "yellow" },
      "anchor": {
        "page_key": "f5d698c04cb99ab4",
        "spine_href": "OEBPS/ch03.xhtml",
        "spine_index": 7,
        "cfi": "epubcfi(/16/4/2/1:0,/16/4/2/1:42)",
        "start": { "dom_path": "/p[12]/text()[1]", "offset": 0, "char": 1234 },
        "end": { "dom_path": "/p[12]/text()[1]", "offset": 42, "char": 1276 },
        "prefix": "up to 32 characters before",
        "suffix": "up to 32 characters after",
        "progression": 0.42
      },
      "origin": {
        "app": "calibre",
        "id": "2f0c…",
        "raw": { "type": "highlight", "uuid": "2f0c…" }
      }
    }
  ]
}
```

Field notes:

- `id` is a UUID. For imported annotations, derive it deterministically from
  `content_id` + origin identity (UUIDv5) so repeated imports do not duplicate.
- `type` is `highlight` or `bookmark`. A note is a highlight with `note` set; a
  standalone note can be represented as a highlight with an empty quote if the
  UI allows it.
- `deleted` is a tombstone. Keep the record for merging; do not purge it unless
  the user explicitly compacts the store.
- `updated` is the merge clock. Use ISO 8601 UTC. Calibre timestamps without a
  timezone should be interpreted as UTC, matching calibre's own merge behavior.
- `anchor` is a **selector set**. Any field may be missing; resolution tries
  them in order.
- `origin.raw` preserves the source record for re-resolution and round-tripping.
  It is not used for rendering and may contain private text, so it stays out of
  the generated site.

### 4.3 Anchor resolution order

At page load:

1. **Exact DOM range** (`dom_path` + offsets) if the generated page has not
   changed. This is fast and exact for a rebuild of the same EPUB.
2. **Source locator**: EPUB CFI or normalized source character range, resolved
   against the source document, then mapped to the generated page.
3. **Text quote** (`quote` + `prefix`/`suffix`) within the expected page,
   chapter, or book. Score candidates by exact quote, context match, and
   distance from `progression`.
4. **Page/chapter progression** as a last resort, only to show "this annotation
   was near here"; require user confirmation before attaching.

If step 3 finds multiple equally good candidates, mark the annotation
`needs_review`; do not pick one at random.

### 4.4 Why not use routes or page keys alone

Routes are positional. A new front-matter page shifts every later route. Page
keys are derived from the source file list, so two pages split from the same
EPUB file can have the same key, and a page split can leave both pages looking
identical to the key. Neither is a stable annotation anchor.

The existing `chapter_key` is useful as a grouping hint, not as a precise
anchor. Store it in the annotation for display, but resolve with text and source
locators.

### 4.5 Why not use EPUB CFI as the only anchor

CFI is the right *interchange* idea: it is source-level, sortable, and
independent of the generated HTML. But:

- calibre's highlight CFIs are relative and non-standard;
- calibre has produced incorrect offsets;
- the CFI depends on the EPUB DOM, not on the text alone;
- a generated page may split a source file at a TOC anchor, so one source range
  can cross two generated pages.

Use CFI as one selector and as the migration input. Use the quote and source
text as the verification layer.

## 5. Where to store annotations

### 5.1 Browser storage is the default

Use **IndexedDB** as the primary local store, with a `localStorage` fallback for
environments where IndexedDB is unavailable.

Why IndexedDB:

- asynchronous, so large note collections do not block the UI;
- structured records and indexes by `content_id` / annotation id;
- larger quota than `localStorage`;
- one record per annotation, so two tabs can merge updates instead of
  overwriting a whole book document.

Suggested stores:

```text
database: epub2web-annotations
  books        keyPath: content_id
  annotations  keyPath: id
               index: content_id
               index: updated
  meta         keyPath: key
```

A single per-book JSON document is acceptable for a first version, but it makes
multi-tab merging and partial writes harder. Per-record storage is a better
long-term shape.

Fallback key if IndexedDB is unavailable:

```text
epub2web:annotations:v1:<content_id>
```

This is a JSON document with the same schema. Keep it under a few megabytes.

### 5.2 Desktop app data is an optional durable copy

For the desktop app, store a copy under the platform application-data directory:

| Platform | Path |
|---|---|
| Linux | `$XDG_DATA_HOME/epub2web/annotations/<content_id>.json`, defaulting to `~/.local/share/epub2web/annotations/<content_id>.json` |
| macOS | `~/Library/Application Support/epub2web/annotations/<content_id>.json` |
| Windows | `%LOCALAPPDATA%\epub2web\annotations\<content_id>.json`, falling back to `%APPDATA%\epub2web\...` |

Do not hardcode `~/.epub2web`. The CLI and GUI should share one
`app_data_dir()` helper that honors `XDG_DATA_HOME`, `LOCALAPPDATA`, `APPDATA`,
and `Path.home()`. This copy survives deleting the generated site, clearing
browser data, and changing the preview port. It is also the natural place for a
future CLI import.

The built-in preview server can serve this file read-only, and optionally accept
writes from the local page. If a write API is added:

- bind only to `127.0.0.1` (already the case);
- require a per-session token or origin check;
- never expose it on a public host;
- keep it optional so a static build still works.

A simpler alternative is the browser's File System Access API: the user chooses
an `annotations.json` file once, and the page reads/writes it directly. This is
not available in every browser, so it should be an enhancement, not the only
path.

### 5.3 Never put private annotations in the generated site

Do not write `annotations.json` into `book-site/` by default. The site is
designed to be publishable, and notes are private. A static file in the output
would be uploaded along with the book.

If public/shared annotations are ever wanted, make that an explicit separate
feature with a clear warning, not a side effect of local highlighting.

### 5.4 What happens when the site is regenerated

The build stages a new directory and swaps it into place
(`epub2web/cli.py`). Browser storage is outside that directory, so a rebuild of
the same EPUB at the same origin keeps annotations automatically.

The difficult cases are:

| Change | What happens | Mitigation |
|---|---|---|
| Same EPUB, same URL | `content_id` and `source_sha256` match | automatic |
| Same EPUB, new output directory or port | new browser origin | import/export or desktop app-data copy |
| EPUB re-zipped or metadata changed | `source_sha256` changes, text unchanged | `content_id` matches |
| EPUB text updated | `content_id` changes | quote resolution; unresolved report |
| TOC split changes page routes | routes change; page keys may collide or stay the same | text/source anchors, not routes or page keys |
| Site published on a new host | new origin | export from the old origin, import on the new one |
| `--force` rebuild | only files change | browser/app-data store untouched |

The existing `reading_id` is intentionally file-specific; the test
`test_reading_id_is_stable_and_file_specific` asserts that a changed EPUB gets a
different id. Do not change that behavior for reading progress. Add
`content_id` as a second, annotation-specific identity.

### 5.5 Multi-tab and merge behavior

- Use `BroadcastChannel` (or the `storage` event for the fallback) to notify
  other tabs of changes.
- Merge per annotation record by `id` and `updated`, not by replacing the whole
  book document.
- Newer timestamp wins. A newer tombstone must not be resurrected by an older
  active record.
- If two tabs edit the same annotation at the same timestamp, keep the one with
  the richer content and record a conflict flag for the UI.

### 5.6 Quota, eviction, and privacy

- Call `navigator.storage.persist()` when the user creates the first
  annotation, and show a small "stored in this browser" note.
- Offer **Export annotations** and remind the user before clearing site data.
- Treat notes as untrusted text. Render with `textContent`, never `innerHTML`.
  If Markdown is supported later, sanitize it with an allowlist.
- Do not include annotation text in search indexes, page metadata, logs, or
  support ZIPs.
- Private browsing and storage eviction can remove the store; the app-data copy
  or an export is the backup.

## 6. Storage format and merge rules

### 6.1 Identity

- New annotations: UUIDv4.
- Imported calibre highlights: UUIDv5 over `content_id`, `"calibre"`, and the
  calibre `uuid`.
- Imported calibre bookmarks: UUIDv5 over `content_id`, `"calibre-bookmark"`,
  and a normalized `(title, pos)` pair, because bookmarks have no UUID.

Also keep `origin.app` and `origin.id`; matching by origin identity makes
re-imports idempotent even if the derived UUID scheme changes.

### 6.2 Merge algorithm

```text
for each incoming record:
    find existing by id, then by (origin.app, origin.id)
    if no existing:
        insert
    else if incoming.updated > existing.updated:
        replace, preserving unknown fields from existing if useful
    else if incoming.updated == existing.updated:
        prefer the record with a resolved anchor; otherwise keep existing
    else:
        ignore incoming
```

Tombstones participate in the same comparison. A deleted record is not the same
as a missing record.

### 6.3 Export

Native export should be the complete document, including tombstones and
`origin.raw`. It is the backup and migration format. The file contains private
quotes and notes, so it must be treated like the book itself and never written
into a published site. Add a human-readable Markdown/plain-text export
separately; do not use it for re-import.

Optional calibre-compatible export:

- `calibre_annotation_collection` when each annotation still has a valid
  `spine_index`/CFI and the same EPUB edition is available;
- otherwise export native JSON plus a warning that calibre cannot place the
  annotations without a CFI.

Round-tripping to calibre is inherently lossy unless the target is the same
EPUB edition and the CFI can be regenerated.

## 7. Migrating from calibre

### 7.1 Source precedence

Read sources in this order, merging rather than replacing:

1. `metadata.db` `annotations` table for the matching book/format/user;
2. the viewer sidecar JSON for the book path;
3. `META-INF/calibre_bookmarks.txt` inside the EPUB;
4. `calibre:annotation` entries in a `metadata.opf` copy;
5. exported JSON files (`calibre_annotation_collection` or
   `calibre_highlights`).

The database is the most complete and current for library books. The sidecar is
the fallback for standalone books. The in-EPUB and OPF copies are portable
snapshots and may be stale; merge by timestamp and tombstones. Libraries from
older calibre versions may not have the `annotations` table at all, in which
case fall back to the sidecar and the in-EPUB/OPF copies.

If several sources disagree, use calibre's rules: newer timestamp wins,
highlights match by UUID, bookmarks by title, and `removed` stays removed.

### 7.2 Zero-touch migration is the default

The user should not have to find calibre's database, run an export, or choose a
file. Treat migration as part of opening the book:

1. When the desktop app builds or opens a book, look for a local calibre
   configuration/library (`metadata.db`) and for the viewer sidecar and in-EPUB
   copies. This is read-only; never modify calibre's files.
2. Match the book by `source_sha256`, `content_id`, ISBN, then title/author.
   If exactly one confident match exists, import it automatically.
3. Merge into the annotation store, show a compact summary such as
   "Imported 42 highlights and 7 notes from calibre", and offer Undo.
4. If the match is ambiguous or an edition changed, show the normal review list;
   do not block the build and do not guess.
5. Remember the import so it is not repeated. Re-import only when the calibre
   source's timestamp or the annotation set changes.

Path discovery must follow platform conventions:

- Never hardcode `~/Calibre Library` or `~/.config/calibre`.
- Use `CALIBRE_CONFIG_DIRECTORY` when set; otherwise use the platform config
  directory from the table in section 2.2.
- Read calibre's configured library path from its own settings. If that is not
  available, check `~/Calibre Library`, `~/Documents/Calibre Library`, and the
  Windows equivalents. Windows `Documents` may be redirected to OneDrive, and
  the folder name may be localized, so treat these as fallbacks rather than
  facts.
- Allow explicit overrides with `EPUB2WEB_CALIBRE_LIBRARY` and
  `--calibre-library`.
- If `metadata.db` is copied, copy its `-wal` and `-shm` sidecars too; otherwise
  recent annotations can be missing. Prefer a read-only SQLite connection with
  a busy timeout over copying a live library.
- On macOS, reads outside the app container can require user permission. On
  WSL, a Windows-side calibre installation is not automatically discoverable;
  point at `/mnt/c/...` or use an export.

For the CLI, the same detection should run by default. The explicit commands
below remain useful for automation, tests, and unusual installs; they are not
the expected user path.

```bash
# Zero-touch default: discover and import a matching calibre library
epub2web book.epub -o book-site

# Explicit paths, for automation or non-standard installs
epub2web annotations import book.epub \
  --calibre-library "$HOME/Calibre Library" \
  --calibre-book-id 42 \
  --output annotations.json

# From a calibre JSON export
calibredb annotations export -f json --search "id:42" > calibre.json
epub2web annotations import book.epub \
  --from calibre.json \
  --output annotations.json

# From the copies inside the EPUB / a metadata.opf
epub2web annotations import book.epub --from-epub
epub2web annotations import book.epub --from-opf metadata.opf

# Dry run, with a machine-readable report
epub2web annotations import book.epub --from calibre.json \
  --dry-run --report annotations-import-report.json
```

`--output` writes the native annotation document. In the desktop app, the same
result is written to the app-data store and served to the preview. In a purely
static setup, the user imports the JSON through the reader's
**Import annotations** control as a fallback.

### 7.3 Resolution algorithm

For each calibre record:

1. **Validate** the shape. Reject unknown/malformed objects into the report;
   do not partially import a bad record.
2. **Find the book.** Compare the calibre book's EPUB to the target by
   `source_sha256`, ISBN, title/author, then allow a manual choice. Do not
   import a different edition without confirmation.
3. **Find the spine item.** Prefer `spine_name` over `spine_index`. If neither
   exists, use the CFI's first step.
4. **Parse the CFI as a hint.** Extract the text offset if possible. Treat
   parse failures as a hint failure, not a reason to drop the record.
5. **Extract the quote.** Prefer `highlighted_text`; fall back to the text
   obtained from the CFI range. Normalize both sides consistently
   (NFC, whitespace, soft hyphens) for comparison, but keep the raw quote.
6. **Map to a page.** Use the source path/spine index to find the page plan and
   its generated page. Search the page text for the quote, then the chapter,
   then the book.
7. **Score the match.** Exact quote plus matching prefix/suffix near the CFI
   position is high confidence. Exact quote with an ambiguous position is
   medium. No quote is unresolved.
8. **Store the selector set** that actually succeeded. Keep the original CFI and
   raw calibre object in `origin.raw` for future re-resolution.
9. **Merge** with existing annotations using the rules above.
10. **Report** imported, unchanged, tombstoned, needs-review, and failed counts,
    with reasons and source locations.

Never silently attach an annotation to the first occurrence of a repeated
phrase. Repeated phrases are common in books; the report and review UI are part
of the feature.

### 7.4 Field mapping

| Calibre | epub2web |
|---|---|
| `type: highlight` | `type: highlight` |
| `type: bookmark` | `type: bookmark` |
| `highlighted_text` | `quote` |
| `notes` | `note` |
| `uuid` | `origin.id` and derived `id` |
| `timestamp` | `created` / `updated` |
| `style.which` | `style.color` or a decoration class |
| `spine_name` / `spine_index` | `anchor.spine_href` / `anchor.spine_index` |
| `start_cfi`, `end_cfi` | `anchor.start.cfi`, `anchor.end.cfi` |
| `toc_family_titles` | display/grouping metadata only |
| `removed` | `deleted: true` |
| bookmarks' `title`, `pos` | `quote`/label and `anchor` |
| `last-read` | not an annotation; optionally migrate to reading progress |

### 7.5 Special cases

- **Deleted annotations:** preserve tombstones. If the only source is a stale
  in-EPUB copy and the database says removed with a newer timestamp, the
  database wins.
- **Notes with no quote:** calibre can create a highlight with a note and little
  or no selected text. Store it as a note anchored at the CFI position; if the
  position cannot be resolved, put it in the review list rather than attaching
  it to a random paragraph.
- **Cross-page highlights:** a calibre highlight can span a TOC split that the
  renderer turns into two pages. Store start and end separately and render the
  intersection on each page.
- **Overlapping highlights:** support them in the data model. For rendering,
  prefer the CSS Custom Highlight API (multiple named highlights can overlap)
  over wrapping every range in `<mark>` elements.
- **Images and figures:** text quotes cannot anchor a region inside an image.
  Keep the CFI/position and show the annotation at the figure or caption
  fallback; do not invent a text quote.
- **Changed edition:** if quotes no longer match, mark unresolved and show the
  original quote and chapter. Do not guess.
- **Duplicate bookmarks:** calibre bookmarks are identified by title; a renamed
  bookmark is a delete plus an add. Follow the same rule on import.

### 7.6 Importing into the browser

A static site cannot write a file next to itself. The practical options are:

1. **Desktop app data (recommended, zero-touch):** the GUI/CLI discovers the
   matching calibre annotations, writes
   `<app data>/epub2web/annotations/<content_id>.json`, and the preview server
   serves it. The page merges it on load; the user only sees a summary and Undo.
2. **File picker (fallback for static hosting):** the reader has
   **Import annotations** and **Export annotations** controls. The user selects
   a native JSON file; the page validates and merges it into IndexedDB.
3. **File System Access API (progressive enhancement):** the user grants access
   to one JSON file; the page reads and writes it directly.

Do not publish the import file with the site.

## 8. Implementation plan for this repository

### Phase 1: identity and schema

- Add `content_id` to `epub2web/generic.py` and `book.json` metadata.
- Add `data-content-id` to the reading pages (alongside `data-reading-id`).
- Add `epub2web/annotations.py` with the schema, validation, merge, tombstone,
  and native export/import functions.
- Add tests for:
  - `content_id` stability across a copied/re-zipped EPUB;
  - `content_id` changes when text changes;
  - merge by id and timestamp;
  - tombstone behavior;
  - malformed import rejection;
  - annotations never appear in the generated site.

### Phase 2: reader UI and local storage

- Add an IndexedDB wrapper with a `localStorage` fallback.
- Add selection handling on `.book-page`, a small highlight toolbar, and a note
  editor.
- Render highlights with the CSS Custom Highlight API, with a `<mark>` fallback
  where necessary.
- Add an annotations panel, per-chapter grouping, jump-to-highlight, edit note,
  delete, and export/import.
- Add `BroadcastChannel`/`storage` synchronization.
- Add keyboard and screen-reader behavior; selection must work without a mouse.
- Test with synthetic EPUB fixtures only.

### Phase 3: robust re-anchoring

- Store DOM range, source locator, quote/prefix/suffix, page key, and
  progression.
- Implement resolution order and `needs_review`.
- Handle page splits and cross-page ranges.
- Add a migration test that regenerates a site with changed routes/TOC splits.

### Phase 4: zero-touch calibre import

- Start with exported JSON (`calibre_annotation_collection` and
  `calibre_highlights`); it is the easiest to test offline.
- Add `metadata.db` reading in read-only mode, then in-EPUB and OPF copies.
- Add automatic discovery and book matching so the normal build/import path
  needs no user input.
- Add a compact "Imported N highlights and M notes from calibre" summary with
  Undo; only surface the review list for ambiguous matches.
- Add dry-run/report output as an automation and debugging escape hatch.
- Add fixture tests using synthetic calibre JSON; do not commit real books.
- Keep the import code independent of the GUI and worker modules.

### Phase 5: desktop durability

- Write the app-data copy.
- Add a localhost-only read endpoint, and optionally a write endpoint with an
  origin check.
- Keep the static site fully functional without the endpoint.

## 9. Open questions

- **Notes without highlights:** should a standalone note be allowed? Calibre
  couples notes to highlights. A separate `note` type is easier for users but
  needs a point anchor and a different list UI.
- **Cross-page selection:** allow it in the UI, or split it into two highlights?
  Calibre highlights are within a spine item, but the generated site may split
  that item.
- **Edition matching:** how much text change is acceptable before requiring
  review? A fuzzy quote match is useful, but a wrong match is worse than an
  unresolved annotation.
- **Storage durability:** is the app-data copy enough, or should the desktop app
  also export a backup on every change?
- **Round-trip expectations:** do users need calibre to see epub2web highlights,
  or only the reverse? Regenerating a correct CFI is the hard part.
- **Search:** should annotation text be searchable locally? If yes, keep it out
  of the published search index.
- **Sharing:** public annotations are a separate product decision with privacy
  and moderation implications.

## 10. Other readers: what calibre support does and does not buy

Calibre is not the only EPUB reader with highlights and notes. It is, however,
one of the few with a documented, local, importable representation. Supporting
calibre builds the shared import pipeline, but it does **not** automatically
support other applications.

### 10.1 The three layers that differ

Every reader differs at three layers:

1. **Storage**: SQLite, JSON, Lua tables, XML, or cloud-only.
2. **Locator dialect**: EPUB CFI, KOReader XPointer, Kobo `point()` paths, DOM
   ranges, page numbers, or plain text with no locator.
3. **Export/import availability**: native JSON export, a database on disk, a
   human-readable export, or only a cloud account.

Calibre support gives us layer 3 for one app and a working implementation of
the shared parts: book matching, text normalization, quote resolution, merge
rules, tombstones, and the review report. Each additional app still needs a
parser for layer 1 and a converter for layer 2.

### 10.2 Reader comparison

This is a practical classification, not a promise that every format is stable.
Vendors change schemas without notice. Treat the paths as discovery hints:
resolve app-data directories per platform, and account for Flatpak/Snap
sandboxes, macOS containers, Windows roaming/local differences, and portable
installations that override their config directory.

| Reader | Where highlights/notes live | Locator | Import difficulty | Notes |
|---|---|---|---|---|
| **Calibre** | `metadata.db` `annotations` table; viewer JSON; optional in-EPUB `META-INF/calibre_bookmarks.txt`; OPF copy; JSON export | Relative EPUB CFI + `spine_index`/`spine_name` | Baseline | Best-documented source; also has `calibredb annotations export/import` |
| **Thorium Reader / Readium apps** | Readium Annotation Set JSON (`.annotation`), W3C Web Annotation profile | CFI, TextQuote, DOM range, progression selectors | Low–medium | Best second adapter; standards-based and includes several selectors at once |
| **Foliate** | One JSON file per book under the Foliate data directory (Linux: `~/.local/share/com.github.johnfactotum.Foliate`; Flatpak/Snap paths differ) | EPUB CFI | Low | Plain JSON, CFI, quote, note, color; easy to parse |
| **Zotero** | Zotero SQLite database; EPUB annotations exposed as WADM through the API | W3C selectors / CFI | Medium | Good for academic workflows; database schema and API need care |
| **KOReader** | `.sdr/metadata.epub.lua` next to the book | XPointer (`/body/DocFragment[...]/.../text().N`) | Medium | Lua-table parser plus XPointer-to-source-offset converter; well-used |
| **Apple Books** | `AEAnnotation*.sqlite` plus `BKLibrary*.sqlite` on macOS | EPUB CFI | Medium | Read-only SQLite copy; CFI parsing; book matching by asset id |
| **Kobo** | `.kobo/KoboReader.sqlite`, `Bookmark` table | Kobo `point(/1/4/...)` paths plus element index/offsets | Medium–hard | Undocumented path dialect; device/firmware differences; sideloaded vs store books differ |
| **Readest** | Native JSON export/backup; sync uses KOReader xpointers for progress | App JSON; xpointer in sync | Medium | Open-source; JSON export is the practical entry point |
| **Adobe Digital Editions** | `.annot` XML files under `Documents/.../Digital Editions/Annotations` | Proprietary XML structure | Medium–hard | Old, undocumented, tied to book filename; still common in libraries |
| **Moon+ Reader** | `.mrexpt` text export, or Android SQLite `mrbooks.db` via backup/root | Chapter title and quote; no precise locator in the text export | Medium | Quote matching is required; export is human-readable, not positional |
| **PocketBook** | Notes exported as HTML from the device/app | Page/quote, no stable EPUB locator | Medium | Treat as text-and-note import with review |
| **Kindle** | `My Clippings.txt`; newer devices also use `ksdk_annotation_v1.db`; store books sync through Amazon | Often no EPUB locator; position only, sometimes no text | Hard / limited | Clipping limits truncate long highlights; no direct EPUB CFI; personal documents are easier |
| **Google Play Books** | Cloud; export to Google Drive/DOCX or Google Takeout | No usable EPUB locator | Hard / limited | Text often truncated by publisher copy limits; unsuitable for precise re-anchoring |
| **Kobo app / Kindle app / Play Books app** | Cloud account | None locally | Not viable without an export | Require a user-provided export first |

### 10.3 Support levels

It helps to define what "support" means for each app:

- **Level 1 — quotes and notes only.** Import the text and note, but require
  the user to place or confirm the location. Suitable for Kindle clippings,
  Google Play Books, PocketBook, and plain-text Moon+ exports.
- **Level 2 — resolved location.** Import and match by quote/context against
  the EPUB, with a confidence score and review UI.
- **Level 3 — native locator.** Import the app's own CFI/XPointer/point locator,
  convert it to the internal source anchor, and preserve it for round-trip.
- **Level 4 — round-trip.** Export annotations back into the other app's format
  and have that app accept them. Calibre is close to this; most readers are not.

Calibre support should target Level 3. Other apps can be added at whatever
level their data allows; do not advertise Level 3 when only Level 1 is possible.

### 10.4 Adapter architecture

Do not put per-app logic in the calibre importer. Introduce a small adapter
interface and keep the shared pipeline app-neutral:

```text
epub2web/annotations/
  model.py          # native Annotation, Locator, merge, tombstones
  normalize.py      # NFC, whitespace, soft hyphen, text quote extraction
  resolve.py        # source offset / CFI / XPointer / point() / quote matching
  merge.py          # UUID/title identity, timestamps, deleted records
  report.py         # imported, unchanged, needs_review, failed
  importers/
    base.py         # Importer protocol
    calibre.py
    readium.py
    foliate.py
    koreader.py
    apple_books.py
    kobo.py
    text_only.py    # Kindle, Google Play, Moon+, PocketBook
```

Each importer should only do four things:

1. **Discover** candidate books and annotations.
2. **Load** raw records without modifying the source.
3. **Normalize** them into the native annotation shape, keeping `origin.raw`.
4. **Provide a locator** in whatever dialect the app uses.

The shared resolver then converts the locator to a source position, maps it to
the generated page, verifies the quote, and merges with existing annotations.

This means:

- A new **CFI-based** reader (Apple Books, Foliate, Thorium, calibre) mostly
  needs a loader; the CFI converter is shared.
- A new **XPointer-based** reader (KOReader, Readest sync) needs one XPointer
  converter; the rest is shared.
- A new **point()-based** reader (Kobo) needs one Kobo path converter.
- A **text-only** reader (Kindle, Google Play, Moon+, PocketBook) needs only a
  parser plus the quote matcher; it will produce Level 1/2 results.

### 10.5 Recommended order

1. **Calibre** — already planned; provides the baseline and merge semantics.
2. **Readium / Thorium Annotation Set** — standards-based and multi-selector;
   the best multiplier for future readers and for export.
3. **Foliate** — simple JSON + CFI; cheap to add and validates the CFI path.
4. **KOReader** — popular and open; adds XPointer support and text matching.
5. **Apple Books and Kobo** — valuable but platform-specific SQLite work;
   build only with real test data and a read-only copy strategy.
6. **Text-only imports** (Kindle, Google Play, Moon+, PocketBook, Readest) —
   import what can be imported, mark locations for review, and never claim
   exact placement when there is none.

### 10.6 What to tell users

A realistic promise is:

> epub2web can import annotations from calibre and from readers that export
> standard or documented formats. Other readers can be supported through
> adapters; some only provide quotes and notes without a reliable location, so
> those imports are reviewed before they are attached.

Do not promise "all EPUB readers". The data simply is not uniformly available,
and some cloud readers deliberately do not expose it.

### 10.7 Legal and maintenance notes

- Calibre, KOReader, and Foliate are GPL-licensed. This project is
  GPL-3.0-or-later, so code reuse is compatible, but preserve copyright notices
  and prefer independent implementations where practical.
- Apple Books, Kobo, Amazon, and Google formats are undocumented and can
  change. Keep each adapter isolated, version-detect where possible, and fail
  with a clear message instead of guessing.
- Always read a copy of a database, never the live file, and never write to
  another application's store.
- Cloud exports require an explicit user action. Do not add runtime network
  access to the build or the reader.

## 11. References

### Calibre

- [`resources/metadata_sqlite.sql`](https://github.com/kovidgoyal/calibre/blob/master/resources/metadata_sqlite.sql) — `annotations` and `last_read_positions` schema.
- [`src/calibre/db/annotations.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/annotations.py) — merge rules, searchable text, export rendering.
- [`src/calibre/db/backend.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/backend.py) — save/load annotation code.
- [`src/calibre/gui2/viewer/annotations.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/gui2/viewer/annotations.py) — sidecar JSON and in-EPUB base64 writing.
- [`src/calibre/gui2/viewer/highlights.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/gui2/viewer/highlights.py) — viewer export and styles.
- [`src/calibre/ebooks/epub/cfi/parse.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/ebooks/epub/cfi/parse.py) — CFI parser and decoder.
- [`src/calibre/ebooks/metadata/opf2.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/ebooks/metadata/opf2.py) — `calibre:annotation` metadata.
- [`src/calibre/db/cli/cmd_annotations.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/db/cli/cmd_annotations.py) — collection export/import.
- [`src/calibre/srv/render_book.py`](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/srv/render_book.py) — `EPUB_FILE_TYPE_MAGIC`.

### Standards and interoperability

- [EPUB Canonical Fragment Identifiers 1.1](https://idpf.org/epub/linking/cfi/epub-cfi.html).
- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) — TextQuoteSelector, TextPositionSelector, RangeSelector.
- [Readium Locator model](https://readium.org/architecture/models/locators/) — `href`, `locations`, and `text.before/highlight/after`.
- [Foliate issue #849](https://github.com/johnfactotum/foliate/issues/849) — calibre CFI quirks and in-EPUB format.

### This repository

- `epub2web/generic.py` — `reading_id`.
- `epub2web/render.py` — page keys, chapter keys, progress.
- `epub2web/theme/assets/app.js` — progress and settings storage.
- `epub2web/templates/base.html` — `data-reading-id`, `data-page-key`, `data-chapter-key`.
- `tests/test_end_to_end.py` — reading id and page key behavior.
