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
from .paths import normalize_base_path
from .progress import ProgressCallback, ProgressPrinter, emit_event
from .render import SITE_MARKER, render_site
from .server import serve_directory
from .text import slugify, split_title
from .verify import verify_site


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
    progress: ProgressCallback | None = None,
) -> dict:
    book = GenericExtractor(epub, content, images, progress=progress, clean_images=True).run()
    if title:
        book["meta"]["title"] = title
        book["meta"]["short_title"], book["meta"]["subtitle"] = split_title(title)
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
        site_url=site_url,
        base_path=base_path,
        progress=progress,
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
    """Return True for an absent/empty output or a marked epub2web site."""
    if not output.exists():
        return True
    try:
        if not any(output.iterdir()):
            return True
    except OSError:
        return False
    return (output / SITE_MARKER).is_file()


def legacy_output_looks_like_site(output: Path) -> bool:
    """Recognize pre-marker sites so ``--force`` can migrate them once."""
    return (output / "index.html").is_file() and (output / "search-index.json").is_file()


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
    parser.add_argument(
        "--report-dir",
        type=Path,
        help="directory for the failure support ZIP (default: ./epub2web-reports)",
    )
    parser.add_argument("--version", action="version", version=f"epub2web {__version__}")
    parser.add_argument(
        "--progress",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    session = setup_logging(log_dir=args.log_dir, log_file=args.log_file)
    argv_for_log = list(sys.argv if argv is None else [sys.argv[0], *argv])
    log_environment(session, argv=argv_for_log)
    session.context["command"] = argv_for_log
    session.info(
        "command parsed",
        output=str(args.output) if args.output else None,
        base_path=args.base_path,
        site_url=args.site_url,
        serve=args.serve,
    )

    status = "error"
    exit_code = 2
    progress = ProgressPrinter() if args.progress else None
    try:
        exit_code = _run(args, parser, session, progress)
        status = "ok" if exit_code == 0 else "failed"
        return exit_code
    except KeyboardInterrupt:
        status = "interrupted"
        exit_code = 130
        session.context["error"] = "interrupted by user"
        session.warning("interrupted by user")
        print("\nStopped.", file=sys.stderr)
        return 130
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        if code != 0:
            status = "usage"
            exit_code = code
            session.context["error"] = f"usage error (exit {code})"
            session.error("command exited with an error", exit_code=code)
        else:
            status = "ok"
            exit_code = 0
        raise
    except Exception as exc:
        status = "error"
        exit_code = 2
        session.context["error"] = str(exc)
        session.exception("command failed", error=str(exc))
        print(f"\nerror: {exc}", file=sys.stderr)
        return 2
    finally:
        session.context.update({"status": status, "exit_code": exit_code})
        session.finish(status, exit_code=exit_code)
        report = None
        if exit_code not in (0, 130):
            report = session.write_support_bundle(
                status=status,
                exit_code=exit_code,
                error=str(session.context.get("error", "")),
                report_dir=args.report_dir,
            )
        if exit_code == 0:
            if args.log_dir or args.log_file:
                _print_log_path(session)
        elif report is not None:
            if progress is not None:
                emit_event("report", report=str(report))
            print(f"Report:  {report}", file=sys.stderr)
            print("         attach this file when reporting the problem", file=sys.stderr)
        else:
            _print_log_path(session)
        session.close()


def _run(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    session: LogSession,
    progress: ProgressPrinter | None = None,
) -> int:
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
        session.context["error"] = f"could not read EPUB: {exc}"
        session.exception("could not read EPUB", error=str(exc))
        print(f"error: could not read EPUB: {exc}", file=sys.stderr)
        return 2
    session.context.update(
        {
            "epub": str(epub),
            "title": info.get("title", ""),
            "author": info.get("author", ""),
        }
    )
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
    session.context.update(
        {
            "output": str(output),
            "site_url": args.site_url,
            "base_path": base_path,
            "profile": "generic",
        }
    )
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
    existing = output.exists()
    nonempty = False
    refresh = False
    if existing:
        try:
            nonempty = any(output.iterdir())
        except OSError as exc:
            parser.error(f"cannot read output directory {output}: {exc}")
        refresh = nonempty and output_looks_like_site(output)
    if existing and not args.force and nonempty and not refresh:
        parser.error(
            f"output already exists and was not created by epub2web: {output}\n"
            "Choose a different folder with -o, or pass --force to replace it. "
            "Sites built by earlier epub2web versions need --force once to add the site marker."
        )
    if args.force and not (output_looks_like_site(output) or legacy_output_looks_like_site(output)):
        parser.error(
            f"refusing to replace {output}: it does not look like an epub2web site "
            f"(missing {SITE_MARKER}, index.html, or search-index.json)"
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
        if refresh:
            print("Output:  refreshing the existing site")

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
            progress=progress,
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
        if progress is not None:
            emit_event(
                "stats",
                pages=len(book.get("pages", [])),
                words=stats.get("words", 0),
                figures=stats.get("figures", 0),
            )

        verified = True
        if not args.no_verify:
            result = verify_site(content, staging, verbose=False, progress=progress)
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
            if progress is not None:
                emit_event(
                    "verify",
                    {"pass": verified},
                    exact=exact,
                    pages=len(result["pages"]),
                    failures=result["failures"],
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
            link_result = check_site_links(staging, base_path=base_path, progress=progress)
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
            if progress is not None:
                emit_event(
                    "links",
                    {"pass": links_ok},
                    checked=link_result["checked"],
                    broken=len(link_result["broken"]),
                    duplicates=len(link_result["duplicates"]),
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
        if progress is not None:
            emit_event("search", sections=search_count)

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
            session.context["error"] = "build rejected by the fidelity or link gate"
            session.error(
                "build rejected by gates",
                fidelity=verified,
                links=links_ok,
                output=str(output),
            )
            print(f"Time:    {elapsed:.2f}s")
            if progress is not None:
                emit_event("time", seconds=round(elapsed, 3))
            return 1

        if progress is not None:
            progress("publish", "Publishing site", 0, 1)
        publish_site(staging, output)
        published = True
        if progress is not None:
            progress("publish", "Publishing site", 1, 1)
        session.write_artifact("summary", summary)
        session.info("site published", output=str(output), package=base_path or "/")
        print(f"Site:    {output / 'index.html'}")
        print(f"Time:    {elapsed:.2f}s")
        if progress is not None:
            emit_event("site", site=str(output / "index.html"))
            emit_event("time", seconds=round(elapsed, 3))

        if args.serve:
            if progress is not None:
                progress("preview", "Starting preview", 1, 1)
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
