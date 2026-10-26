"""Command-line entry point for the deterministic EPUB → HTML pipeline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .epub import Epub
from .generic import GenericExtractor
from .links import check_site_links
from .render import render_site
from .text import slugify
from .verify import verify_site

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "templates"
THEME = Path(__file__).resolve().parent / "theme"


def detect(path: Path) -> dict:
    with Epub(path) as book:
        md = book.metadata
    title = md.get("title", "")
    isbn = md.get("isbn", "")
    return {
        "title": title,
        "author": md.get("creator", ""),
        "isbn": isbn,
        "doet": isbn == "9780465072996" or "design of everyday things" in title.lower(),
    }


def run_doet(epub: Path, content: Path, images: Path, output: Path, site_url: str) -> None:
    extract = ROOT / "scripts" / "extract.py"
    build = ROOT / "scripts" / "build.py"
    if not extract.exists() or not build.exists():
        raise RuntimeError("DOET profile scripts are not available in this installation")
    env = os.environ.copy()
    env.update({
        "EPUB_PATH": str(epub),
        "CONTENT_DIR": str(content),
        "IMAGES_DIR": str(images),
        "DIST_DIR": str(output),
        "SITE_URL": site_url,
        "STATIC_DIR": str(ROOT / "static"),
        "TEMPLATES_DIR": str(ROOT / "templates"),
        "PUBLIC_DIR": str(ROOT / "public"),
    })
    subprocess.run([sys.executable, str(extract)], env=env, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(build)], env=env, check=True, stdout=subprocess.DEVNULL)


def run_generic(epub: Path, content: Path, images: Path, output: Path, site_url: str,
                title: str = "", author: str = "") -> dict:
    book = GenericExtractor(epub, content, images).run()
    if title or author:
        book["meta"]["title"] = title or book["meta"]["title"]
        if title:
            book["meta"]["short_title"] = title.split(":")[0].strip() or title
        book["meta"]["author"] = author or book["meta"].get("author", "")
        (content / "book.json").write_text(
            json.dumps(book, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    render_site(content, output, templates_dir=TEMPLATES, static_dir=THEME, site_url=site_url)
    return book


def run_pagefind(output: Path) -> bool:
    candidates = [ROOT / "node_modules" / ".bin" / "pagefind"]
    which = shutil.which("pagefind")
    if which:
        candidates.append(Path(which))
    binary = next((p for p in candidates if p.exists()), None)
    if binary is None:
        return False
    subprocess.run([str(binary), "--site", str(output), "--output-subdir", "pagefind"],
                   check=True, stdout=subprocess.DEVNULL)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="epub2web",
        description="Convert an EPUB into a complete, browser-optimized static website. "
                    "Deterministic: no network calls, no LLM, no prose rewriting.",
    )
    parser.add_argument("epub", type=Path, help="input .epub")
    parser.add_argument("-o", "--output", type=Path, help="output site directory")
    parser.add_argument("--profile", choices=("auto", "generic", "doet"), default="auto",
                        help="extraction profile (default: auto-detect)")
    parser.add_argument("--title", default="", help="override the book title")
    parser.add_argument("--author", default="", help="override the author")
    parser.add_argument("--site-url", default="http://localhost:4321",
                        help="absolute URL used in metadata/sitemap")
    parser.add_argument("--no-search", action="store_true", help="skip the Pagefind index")
    parser.add_argument("--no-verify", action="store_true", help="skip the fidelity gate")
    parser.add_argument("--no-links", action="store_true", help="skip the internal link check")
    parser.add_argument("--force", action="store_true", help="replace an existing output directory")
    parser.add_argument("--keep-work", action="store_true", help="keep the intermediate content directory")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    epub = args.epub.resolve()
    if not epub.exists():
        parser.error(f"no such file: {epub}")

    try:
        info = detect(epub)
    except Exception as exc:
        print(f"error: could not read EPUB: {exc}", file=sys.stderr)
        return 2

    profile = args.profile
    if profile == "auto":
        profile = "doet" if info["doet"] and (ROOT / "scripts" / "extract.py").exists() else "generic"

    slug = slugify(args.title or info["title"] or epub.stem) or "book"
    output = (args.output or Path.cwd() / f"{slug}-site").resolve()
    if output.exists():
        if not args.force:
            parser.error(f"output already exists: {output} (use --force to replace it)")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="epub2web-"))
    content = work / "content"
    images = work / "images"
    site_url = args.site_url.rstrip("/")

    try:
        print(f"EPUB:    {info['title'] or epub.name}")
        if info.get("author"):
            print(f"Author:  {info['author']}")
        print(f"Profile: {profile}")

        if profile == "doet":
            run_doet(epub, content, images, output, site_url)
        else:
            run_generic(epub, content, images, output, site_url, args.title, args.author)

        book = json.loads((content / "book.json").read_text(encoding="utf-8"))
        stats = book.get("stats", {})
        print(f"Pages:   {len(book.get('pages', []))}")
        print(f"Words:   {stats.get('words', 0):,}")
        if stats.get("figures"):
            print(f"Figures: {stats['figures']}")
        print(f"Site:    {output / 'index.html'}")

        verified = True
        if not args.no_verify:
            result = verify_site(content, output, verbose=False)
            verified = result["pass"]
            print(f"Verify:  {'PASS' if verified else 'FAIL'} "
                  f"({len(result['pages']) - result['failures']}/{len(result['pages'])} pages exact)")
            if not verified:
                for row in result["pages"]:
                    if row["status"] != "ok":
                        print(f"  ✗ {row['page']}: {row['title']} ({row['source_tokens']} → {row['output_tokens']} tokens)")
        else:
            print("Verify:  skipped")

        links_ok = True
        if not args.no_links:
            link_result = check_site_links(output)
            links_ok = link_result["ok"]
            print(f"Links:   {'PASS' if links_ok else 'FAIL'} "
                  f"({link_result['checked']:,} checked, {len(link_result['broken'])} broken, "
                  f"{len(link_result['duplicates'])} duplicate ids)")
            if not links_ok:
                for item in link_result["broken"][:10]:
                    print(f"  ✗ {item['file']} -> {item['href']} ({item['reason']})")
                for item in link_result["duplicates"][:10]:
                    print(f"  ✗ {item['file']} duplicate id #{item['id']}")
        else:
            print("Links:   skipped")

        if not args.no_search:
            try:
                if run_pagefind(output):
                    print("Search:  Pagefind index built")
                else:
                    print("Search:  skipped (Pagefind not installed; search will be unavailable)")
            except Exception as exc:
                print(f"Search:  skipped (Pagefind failed: {exc})")
        else:
            print("Search:  skipped")

        elapsed = time.perf_counter() - started
        print(f"Time:    {elapsed:.2f}s")
        if not verified or not links_ok:
            return 1
        return 0
    except Exception as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 2
    finally:
        if args.keep_work:
            print(f"Work:    {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
