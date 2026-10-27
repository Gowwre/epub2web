"""Command-line entry point for epub2web."""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .epub import Epub
from .generic import GenericExtractor
from .links import check_site_links
from .logging import LogSession, log_environment, log_path_for_user, setup_logging
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
        short_title, separator, subtitle = title.partition(":")
        book["meta"]["short_title"] = short_title.strip() or title
        book["meta"]["subtitle"] = subtitle.strip() if separator else ""
        book["meta"]["title_lines"] = []
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


def configure_console() -> None:
    """Use UTF-8 for console output so non-Latin titles do not crash on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(Exception):
            reconfigure(encoding="utf-8", errors="replace")


def validate_site_url(value: str) -> str:
    value = (value or "").strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("--site-url must be an absolute http:// or https:// URL")
    if parts.query or parts.fragment or "?" in value or "#" in value:
        raise ValueError("--site-url must not include a query string or fragment")
    if any(char.isspace() for char in value) or any(char in "<>\"'`" for char in value):
        raise ValueError("--site-url contains unsafe characters")
    return value


def check_output(output: Path, epub: Path) -> None:
    """Refuse output paths whose replacement could destroy source data or a home."""
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    if cwd.is_relative_to(output):
        raise ValueError(
            f"refusing to replace {output}: it contains the current directory; "
            "choose a dedicated output folder"
        )
    if home.is_relative_to(output):
        raise ValueError(
            f"refusing to replace {output}: it contains the home directory; "
            "choose a dedicated output folder"
        )
    if epub.is_relative_to(output):
        raise ValueError(
            f"refusing to replace {output}: it contains the input EPUB; "
            "choose a dedicated output folder"
        )
    if output.exists() and not output.is_dir():
        raise ValueError(f"output path exists and is not a directory: {output}")


def output_looks_like_site(output: Path) -> bool:
    if not output.exists():
        return True
    try:
        if not any(output.iterdir()):
            return True
    except OSError:
        return False
    return (output / "index.html").exists() and (output / "search-index.json").exists()


def publish_site(staging: Path, output: Path) -> None:
    """Move a fully verified build into place, restoring the old site on failure."""
    staging.chmod(0o755)
    if not output.exists():
        staging.rename(output)
        return
    backup = Path(tempfile.mkdtemp(prefix=f".{output.name}-old-", dir=output.parent))
    backup.rmdir()
    output.rename(backup)
    try:
        staging.rename(output)
    except Exception:
        backup.rename(output)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _print_log_path(session: LogSession) -> None:
    path = log_path_for_user(session)
    if path:
        print(f"Log:     {path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    configure_console()
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
    parser.add_argument(
        "--force", action="store_true", help="replace an existing epub2web output directory"
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="keep extraction files and a failed site for inspection",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="directory for run logs (default: ~/.epub2web/logs)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="write this run's human-readable log to an exact file",
    )
    parser.add_argument("--version", action="version", version=f"epub2web {__version__}")
    args = parser.parse_args(argv)

    session = setup_logging(log_dir=args.log_dir, log_file=args.log_file)
    argv_for_log = list(sys.argv if argv is None else [sys.argv[0], *argv])
    log_environment(session, argv=argv_for_log)
    session.info(
        "command parsed",
        output=str(args.output) if args.output else None,
        base_path=args.base_path,
        site_url=args.site_url,
        serve=args.serve,
    )

    status = "error"
    exit_code = 2
    try:
        exit_code = _run(args, parser, session)
        status = "ok" if exit_code == 0 else "failed"
        if exit_code != 0 or args.log_dir or args.log_file:
            _print_log_path(session)
        return exit_code
    except KeyboardInterrupt:
        status = "interrupted"
        exit_code = 130
        session.warning("interrupted by user")
        print("\nStopped.", file=sys.stderr)
        _print_log_path(session)
        return 130
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        if code != 0:
            status = "usage"
            exit_code = code
            session.error("command exited with an error", exit_code=code)
            _print_log_path(session)
        else:
            status = "ok"
            exit_code = 0
        raise
    except Exception as exc:
        status = "error"
        exit_code = 2
        session.exception("command failed", error=str(exc))
        print(f"\nerror: {exc}", file=sys.stderr)
        _print_log_path(session)
        return 2
    finally:
        session.finish(status, exit_code=exit_code)
        session.close()


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser, session: LogSession) -> int:
    started = time.perf_counter()
    try:
        base_path = normalize_base_path(args.base_path)
    except ValueError as exc:
        parser.error(str(exc))
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    try:
        site_url = validate_site_url(args.site_url)
    except ValueError as exc:
        parser.error(str(exc))

    epub = args.epub.expanduser().resolve()
    if not epub.exists():
        parser.error(f"no such file: {epub}")
    if not epub.is_file():
        parser.error(f"not a file: {epub}")

    try:
        info = detect(epub)
    except Exception as exc:
        session.exception("could not read EPUB", error=str(exc))
        print(f"error: could not read EPUB: {exc}", file=sys.stderr)
        return 2
    session.info(
        "EPUB detected",
        epub=str(epub),
        title=info.get("title", ""),
        author=info.get("author", ""),
        bytes=epub.stat().st_size,
    )

    title_for_slug = args.title or info["title"] or ""
    slug = slugify(title_for_slug, fallback="") if title_for_slug else ""
    if not slug:
        slug = slugify(epub.stem, fallback="") or "book"
    output = (args.output.expanduser() if args.output else Path.cwd() / f"{slug}-site").resolve()
    session.info(
        "output selected",
        output=str(output),
        site_url=args.site_url,
        base_path=base_path,
        force=args.force,
    )
    try:
        check_output(output, epub)
    except ValueError as exc:
        parser.error(str(exc))
    if output.exists() and not args.force:
        try:
            if any(output.iterdir()):
                parser.error(f"output already exists: {output} (use --force to replace it)")
        except OSError as exc:
            parser.error(f"cannot read output directory {output}: {exc}")
    if args.force and not output_looks_like_site(output):
        parser.error(
            f"refusing to replace {output}: it does not look like an epub2web site "
            "(missing index.html or search-index.json)"
        )

    work: Path | None = None
    staging: Path | None = None
    published = False
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="epub2web-"))
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-build-", dir=output.parent))
        content = work / "content"
        images = work / "images"
        session.info(
            "workspace created",
            work=str(work),
            staging=str(staging),
            output=str(output),
        )

        print(f"EPUB:    {info['title'] or epub.name}")
        if info.get("author"):
            print(f"Author:  {info['author']}")

        session.info(
            "build started",
            title=info.get("title", ""),
            author=info.get("author", ""),
            output=str(output),
            site_url=site_url,
            base_path=base_path,
        )
        build(
            epub,
            staging,
            content,
            images,
            site_url,
            args.title,
            args.author,
            base_path,
        )
        book = json.loads((content / "book.json").read_text(encoding="utf-8"))
        stats = book.get("stats", {})
        session.info(
            "book parsed",
            pages=len(book.get("pages", [])),
            words=stats.get("words", 0),
            figures=stats.get("figures", 0),
            images=stats.get("images", 0),
        )
        print(f"Pages:   {len(book.get('pages', []))}")
        print(f"Words:   {stats.get('words', 0):,}")
        if stats.get("figures"):
            print(f"Figures: {stats['figures']}")

        verified = True
        if not args.no_verify:
            result = verify_site(content, staging, verbose=False)
            verified = result["pass"]
            exact = sum(1 for row in result["pages"] if row["status"] == "ok")
            session.info(
                "fidelity gate",
                status="pass" if verified else "fail",
                exact=exact,
                pages=len(result["pages"]),
                failures=result["failures"],
            )
            session.write_artifact("fidelity", result)
            print(
                f"Verify:  {'PASS' if verified else 'FAIL'} ({exact}/{len(result['pages'])} pages exact)"
            )
            if not verified:
                for row in result["pages"]:
                    if row["status"] != "ok":
                        print(
                            f"  ✗ {row['page']}: {row['title']} — {row['status']} "
                            f"({row['source_tokens']} → {row['output_tokens']} tokens, "
                            f"{row['source_images']} → {row['output_images']} images)"
                        )
                        if row["detail"]:
                            print(row["detail"])
                for key, check in result.get("checks", {}).items():
                    if check["expected"] != check["actual"]:
                        print(f"  ✗ {key}: expected {check['expected']} / actual {check['actual']}")
        else:
            print("Verify:  skipped")

        links_ok = True
        if not args.no_links:
            link_result = check_site_links(staging, base_path=base_path)
            links_ok = link_result["ok"]
            session.info(
                "link gate",
                status="pass" if links_ok else "fail",
                checked=link_result["checked"],
                broken=len(link_result["broken"]),
                duplicates=len(link_result["duplicates"]),
            )
            session.write_artifact("links", link_result)
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
        search_index = staging / "search-index.json"
        if search_index.exists():
            search_count = len(json.loads(search_index.read_text(encoding="utf-8")))
        session.info("search index", entries=search_count)
        print(f"Search:  {search_count:,} sections indexed")

        elapsed = time.perf_counter() - started
        summary = {
            "status": "ok" if verified and links_ok else "failed",
            "duration_s": round(elapsed, 3),
            "epub": str(epub),
            "title": info.get("title", ""),
            "author": info.get("author", ""),
            "output": str(output),
            "site_url": site_url,
            "base_path": base_path,
            "pages": len(book.get("pages", [])),
            "words": stats.get("words", 0),
            "figures": stats.get("figures", 0),
            "images": stats.get("images", 0),
            "verify": {
                "enabled": not args.no_verify,
                "pass": verified,
            },
            "links": {
                "enabled": not args.no_links,
                "pass": links_ok,
            },
            "search_sections": search_count,
        }
        if not verified or not links_ok:
            session.write_artifact("summary", summary)
            session.error(
                "build rejected by gates",
                fidelity=verified,
                links=links_ok,
                output=str(output),
            )
            print(f"Time:    {elapsed:.2f}s")
            return 1

        publish_site(staging, output)
        published = True
        session.write_artifact("summary", summary)
        session.info("site published", output=str(output), package=base_path or "/")
        print(f"Site:    {output / 'index.html'}")
        print(f"Time:    {elapsed:.2f}s")

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
    finally:
        if work is not None:
            if args.keep_work:
                print(f"Work:    {work}")
            else:
                shutil.rmtree(work, ignore_errors=True)
        if staging is not None and staging.exists():
            if args.keep_work and not published:
                print(f"Failed site kept at: {staging}")
            else:
                shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
