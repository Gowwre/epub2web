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

The download links intentionally point at
[the latest GitHub release](https://github.com/Gowwre/epub2web/releases/latest)
rather than hard-coding asset filenames, since release assets include the
version number. The first-launch FAQ mirrors the instructions in the project
README and `docs/gui.md`.

The screenshots come from `docs/` at the repository root and are checked in here
as optimized WebP files. The social card is `public/og.png`; rebuild it if the
headline or palette changes.
