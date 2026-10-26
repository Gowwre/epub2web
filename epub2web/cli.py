"""Command-line entry point for epub2web."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .epub import Epub
from .generic import GenericExtractor
from .links import check_site_links
from .render import normalize_base_path, render_site
from .server import serve_directory
from .text import slugify
from .verify import verify_site

TEMPLATES = Path(__file__).resolve().parent / "templates"
THEME = Path(__file__).resolve().parent / "theme"


def detect(path: Path) -> dict:
    with Epub(path) as book:
        metadata = book.metadata
    return {
        "title": metadata.get("title", ""),
        "author": metadata.get("creator", ""),
    }


def build(
    epub: Path,
    output: Path,
    content: Path,
    images: Path,
    site_url: str,
    title: str = "",
    author: str = "",
    base_path: str = "",
) -> dict:
    book = GenericExtractor(epub, content, images).run()
    if title:
        book["meta"]["title"] = title
        book["meta"]["short_title"] = title.split(":")[0].strip() or title
    if author:
        book["meta"]["author"] = author
    if title or author:
        (content / "book.json").write_text(
            json.dumps(book, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    render_site(
        content,
        output,
        templates_dir=TEMPLATES,
        static_dir=THEME,
        site_url=site_url,
        base_path=base_path,
    )
    return book


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="epub2web",
        description="Turn an EPUB into a beautiful, browser-optimized static website. "
        "Deterministic: no LLM, no network calls, no prose rewriting.",
    )
    parser.add_argument("epub", type=Path, help="input .epub file")
    parser.add_argument("-o", "--output", type=Path, help="output site directory")
    parser.add_argument("--title", default="", help="override the book title")
    parser.add_argument("--author", default="", help="override the author")
    parser.add_argument(
        "--site-url",
        default="http://localhost:8000",
        help="absolute URL used in metadata and the sitemap",
    )
    parser.add_argument(
        "--base-path",
        default="",
        metavar="PATH",
        help="build for a subpath, e.g. /epub2web (default: site root)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="serve the result locally and open a browser after building",
    )
    parser.add_argument("--port", type=int, default=8000, help="preview port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    parser.add_argument("--no-verify", action="store_true", help="skip the fidelity gate")
    parser.add_argument("--no-links", action="store_true", help="skip the internal link check")
    parser.add_argument("--force", action="store_true", help="replace an existing output directory")
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="keep the intermediate content directory",
    )
    parser.add_argument("--version", action="version", version=f"epub2web {__version__}")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    try:
        base_path = normalize_base_path(args.base_path)
    except ValueError as exc:
        parser.error(str(exc))
    epub = args.epub.resolve()
    if not epub.exists():
        parser.error(f"no such file: {epub}")

    try:
        info = detect(epub)
    except Exception as exc:
        print(f"error: could not read EPUB: {exc}", file=sys.stderr)
        return 2

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

    try:
        print(f"EPUB:    {info['title'] or epub.name}")
        if info.get("author"):
            print(f"Author:  {info['author']}")

        build(
            epub,
            output,
            content,
            images,
            args.site_url.rstrip("/"),
            args.title,
            args.author,
            base_path,
        )
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
            print(
                f"Verify:  {'PASS' if verified else 'FAIL'} "
                f"({len(result['pages']) - result['failures']}/{len(result['pages'])} pages exact)"
            )
            if not verified:
                for row in result["pages"]:
                    if row["status"] != "ok":
                        print(
                            f"  ✗ {row['page']}: {row['title']} "
                            f"({row['source_tokens']} → {row['output_tokens']} tokens)"
                        )
        else:
            print("Verify:  skipped")

        links_ok = True
        if not args.no_links:
            link_result = check_site_links(output, base_path=base_path)
            links_ok = link_result["ok"]
            print(
                f"Links:   {'PASS' if links_ok else 'FAIL'} "
                f"({link_result['checked']:,} checked, {len(link_result['broken'])} broken, "
                f"{len(link_result['duplicates'])} duplicate ids)"
            )
            if not links_ok:
                for item in link_result["broken"][:10]:
                    print(f"  ✗ {item['file']} -> {item['href']} ({item['reason']})")
                for item in link_result["duplicates"][:10]:
                    print(f"  ✗ {item['file']} duplicate id #{item['id']}")
        else:
            print("Links:   skipped")

        search_count = 0
        search_index = output / "search-index.json"
        if search_index.exists():
            search_count = len(json.loads(search_index.read_text(encoding="utf-8")))
        print(f"Search:  {search_count:,} sections indexed")

        print(f"Time:    {time.perf_counter() - started:.2f}s")
        if not verified or not links_ok:
            return 1

        if args.serve:
            serve_directory(
                output,
                port=args.port,
                open_browser=not args.no_browser,
                base_path=base_path,
            )
        else:
            print(f"Preview: epub2web {epub.name} --serve")
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
