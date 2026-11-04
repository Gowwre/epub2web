# epub2web landing site

The public-facing landing page and download page for
[epub2web](https://github.com/Gowwre/epub2web), built with
[Astro](https://astro.build/).

The design uses the reader's own visual language: warm paper, rust ink,
Fraunces for display, Inter for the interface, and Literata inside reading
excerpts. The landing page is deliberately product-first: real reader
screenshots, one build colophon, and a quiet bento grid instead of decorative
chrome. The fonts are bundled from `src/assets/fonts/`; the screenshots and
social card are self-hosted. The site has no client-side framework or runtime
services.

The site ships in English at `/` and Vietnamese at `/vi/`. The header language
button swaps to the same page in the other language, and every page declares
`hreflang` alternates.

On a first visit to an English page, the site checks the system or browser
language. A preferred Vietnamese locale opens the same page under `/vi/`; every
other language stays in English. The redirect preserves the query string and
hash. Clicking the language switch stores the choice in `localStorage` under
`epub2web-ui-lang`, the same preference the generated reader uses, so an
explicit English or Vietnamese choice is not overridden by later detection.
Vietnamese pages remain reachable directly at `/vi/`.

## Development

```bash
cd site
npm install
npm run dev
```

## Build

```bash
npm run build
npm run preview
```

Astro writes the static site to `site/dist/`. Deploy that folder to any static
host. If you deploy to a canonical public URL, set `SITE_URL` at build time so
the canonical and social metadata are absolute:

```bash
SITE_URL=https://epub2web.example npm run build
```

Set `BASE_PATH` when the site is served from a subpath:

```bash
BASE_PATH=/epub2web SITE_URL=https://gowwre.github.io npm run build
```

## GitHub Pages

The [Pages workflow](../.github/workflows/pages.yml) deploys the landing site at
`https://gowwre.github.io/epub2web/` and the generated demo at
`https://gowwre.github.io/epub2web/demo/`. It builds the landing site with
`BASE_PATH=/epub2web`, stages it as the artifact root, then builds the demo into
`/demo` with `--base-path /epub2web/demo`.

All root-relative routes, public assets, fonts, and the social image are
base-path aware. Use `withBase()` from `src/consts.ts` for any new internal link
or file in `public/`.

## Content

The download page resolves the latest release at build time and links directly
to the Windows, macOS, and Linux installer files. It never sends readers to a
release page to find a download. The Pages workflow runs the resolver before
each build, and the release workflow dispatches Pages after publishing a new
release.

The page also detects the visitor’s platform in the browser. It recommends and
highlights the matching direct download, including Intel versus Apple Silicon
macOS when client hints expose the architecture. Phones, ChromeOS, ARM Linux,
and unknown agents get a neutral “choose your platform” state. Without
JavaScript, the page falls back to the same platform picker.

Clicking any download button starts the file and opens a short first-launch
guide for that platform, so the Windows SmartScreen and macOS Gatekeeper steps
are visible without scrolling to the guide section. The native dialog closes
with Escape, the close button, or a backdrop click.

Refresh the committed fallback data locally with:

```bash
npm run update-release
```

This writes `src/data/latest-release.json` from the latest GitHub release. The
script fails if any expected platform asset or `SHA256SUMS.txt` is missing.

The first-launch FAQ mirrors the instructions in the project README and
`docs/gui.md`.

## Languages

English copy lives in `src/i18n/en.ts`; Vietnamese copy lives in
`src/i18n/vi.ts` and is typed against the English table, so missing keys are
TypeScript errors. Pages are thin route wrappers around shared page components:

- `/` and `/vi/` render `HomePage.astro`.
- `/download/` and `/vi/download/` render `DownloadPage.astro`.
- `/changelog/` and `/vi/changelog/` render `ChangelogPage.astro`.

Use `localePath()` and `localeHref()` from `src/i18n/` for internal links so
the locale prefix and `BASE_PATH` stay correct. External links stay unchanged.
Vietnamese pages preload the Vietnamese Fraunces, Inter, and Literata subsets;
the `@font-face` rules are in `src/styles/global.css`.

When adding a string, add it to both `en.ts` and `vi.ts`. Keep translations
natural and concise; do not translate book excerpts, product names, commands,
or file names. The canonical English copy remains the source of truth.

## Changelog page

The `/changelog/` page reads the repository `CHANGELOG.md` at build time and
renders every published release, which is why the build must run from `site/`.
Each version gets a button to its GitHub release. Version 0.1.0 predates the
repository's GitHub Releases history, so its button opens the 0.1.0 section in
the GitHub-hosted changelog instead.

The Pages workflow rebuilds when either changelog changes. Release sections must
use the heading format `## 0.2.0 - 2026-10-28`; the `Unreleased` section is not
published on the site.

### Release notes in two languages

GitHub Releases stay canonical in English. The Vietnamese site reads
`CHANGELOG.vi.md` in the repository root and merges it with the English
changelog, version by version:

- A translated release is used only when its version and date match the
  English release.
- Missing or stale translations fall back to the English notes and show an
  “English only” badge and notice, so a new release is never blocked by a
  translation.
- The English page links to `CHANGELOG.md`; the Vietnamese page links to
  `CHANGELOG.vi.md`. Both remain readable on GitHub.

This follows the pattern used by many mature open-source projects: keep one
canonical release feed for automation and GitHub, publish localized release
pages separately, and allow per-release fallback while translations catch up.
Do not translate version numbers, dates, commands, release tags, or issue IDs.
When adding a release, copy its section into `CHANGELOG.vi.md` under the same
heading and translate the prose; the site checks the version and date before
using it.

The screenshots come from `docs/` at the repository root and are checked in here
as optimized WebP files. `search-panel.webp` is cropped from `docs/search.png`
so the search card shows the panel without its dimmed backdrop. The social card
is `public/og.png`; rebuild it if the headline or palette changes.
