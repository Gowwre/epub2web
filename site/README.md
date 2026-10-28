# epub2web landing site

The public-facing landing page and download page for
[epub2web](https://github.com/Gowwre/epub2web), built with
[Astro](https://astro.build/).

The design reuses the reader's own visual language: warm paper, rust ink,
Fraunces display type, Literata reading type, and Inter for the interface. The
fonts are bundled from `src/assets/fonts/`; the screenshots and social card are
self-hosted. The site has no client-side framework or runtime services.

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

Refresh the committed fallback data locally with:

```bash
npm run update-release
```

This writes `src/data/latest-release.json` from the latest GitHub release. The
script fails if any expected platform asset or `SHA256SUMS.txt` is missing.

The first-launch FAQ mirrors the instructions in the project README and
`docs/gui.md`.

## Changelog page

The `/changelog/` page reads the repository `CHANGELOG.md` at build time and
renders every published release, which is why the build must run from `site/`.
Each version gets a button to its GitHub release. Version 0.1.0 predates the
repository's GitHub Releases history, so its button opens the 0.1.0 section in
the GitHub-hosted changelog instead.

The Pages workflow rebuilds when `CHANGELOG.md` changes. Release sections must
use the heading format `## 0.2.0 - 2026-10-28`; the `Unreleased` section is not
published on the site.

The screenshots come from `docs/` at the repository root and are checked in here
as optimized WebP files. The social card is `public/og.png`; rebuild it if the
headline or palette changes.
