"""Command-line entry point for the deterministic EPUB → HTML pipeline."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import __version__
from .epub import Epub
from .generic import GenericExtractor
from .links import check_site_links
from .logging import LogSession, log_environment, log_path_for_user, setup_logging
from .render import render_site
from .serve import DEFAULT_PORT, serve_site
from .text import slugify
from .verify import verify_site

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "templates"
THEME = Path(__file__).resolve().parent / "theme"
SITE_MARKER = ".epub2web-site.json"


def _port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be a whole number") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _looks_like_epub2web_site(path: Path) -> bool:
    """Recognize sites produced by this tool so a rerun can refresh them safely."""
    if (path / SITE_MARKER).is_file():
        return True
    index = path / "index.html"
    try:
        with index.open(encoding="utf-8", errors="replace") as handle:
            head = handle.read(65_536)
    except OSError:
        return False
    if "epub2web-theme" in head or 'name="generator" content="epub2web"' in head:
        return True

    # Sites built before the marker existed used the shared reader theme.
    app = path / "assets" / "app.js"
    try:
        with app.open(encoding="utf-8", errors="replace") as handle:
            app_head = handle.read(1_024)
    except OSError:
        return False
    return "browser edition" in app_head and "data-theme-toggle" in head


def _create_staging(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f".{output.name}.epub2web-", dir=output.parent))


def _publish_site(staging: Path, output: Path) -> None:
    if output.is_symlink() or output.is_file():
        output.unlink()
    elif output.exists():
        shutil.rmtree(output)
    os.replace(staging, output)


def _write_site_marker(site: Path, info: dict, profile: str, pages: int) -> None:
    marker = {
        "generator": "epub2web",
        "version": __version__,
        "title": info.get("title", ""),
        "author": info.get("author", ""),
        "profile": profile,
        "pages": pages,
    }
    (site / SITE_MARKER).write_text(
        json.dumps(marker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(Exception):
            reconfigure(encoding="utf-8", errors="replace")


def _print_log_path(session: LogSession) -> None:
    path = log_path_for_user(session)
    if path:
        print(f"Log:     {path}", file=sys.stderr)


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


def _run_stage(session: LogSession, name: str, command: list[str], env: dict) -> None:
    session.info("stage started", stage=name, command=shlex.join(command))
    started = time.monotonic()
    proc = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    lines = 0
    for line in proc.stdout:
        lines += 1
        print(line, end="", flush=True)
        session.info("stage output", stage=name, line=line.rstrip("\n"))
    code = proc.wait()
    elapsed = round(time.monotonic() - started, 3)
    session.info("stage finished", stage=name, exit=code, duration_s=elapsed, lines=lines)
    if code != 0:
        raise RuntimeError(f"{name} failed with exit code {code}")


def run_doet(
    epub: Path,
    content: Path,
    images: Path,
    output: Path,
    site_url: str,
    session: LogSession,
) -> None:
    extract = ROOT / "scripts" / "extract.py"
    build = ROOT / "scripts" / "build.py"
    if not extract.exists() or not build.exists():
        raise RuntimeError("DOET profile scripts are not available in this installation")
    env = os.environ.copy()
    env.update(
        {
            "EPUB_PATH": str(epub),
            "CONTENT_DIR": str(content),
            "IMAGES_DIR": str(images),
            "DIST_DIR": str(output),
            "SITE_URL": site_url,
            "STATIC_DIR": str(ROOT / "static"),
            "TEMPLATES_DIR": str(ROOT / "templates"),
            "PUBLIC_DIR": str(ROOT / "public"),
            "PYTHONUNBUFFERED": "1",
        }
    )
    _run_stage(session, "doet-extract", [sys.executable, str(extract)], env)
    _run_stage(session, "doet-render", [sys.executable, str(build)], env)


def run_generic(
    epub: Path,
    content: Path,
    images: Path,
    output: Path,
    site_url: str,
    title: str = "",
    author: str = "",
) -> dict:
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


def run_pagefind(output: Path, session: LogSession) -> bool:
    candidates = [ROOT / "node_modules" / ".bin" / "pagefind"]
    which = shutil.which("pagefind")
    if which:
        candidates.append(Path(which))
    binary = next((p for p in candidates if p.exists()), None)
    if binary is None:
        session.warning("pagefind is not installed; search index will be unavailable")
        return False
    _run_stage(
        session,
        "pagefind",
        [str(binary), "--site", str(output), "--output-subdir", "pagefind"],
        os.environ.copy(),
    )
    return True


def main(argv: list[str] | None = None) -> int:
    configure_console()
    parser = argparse.ArgumentParser(
        prog="epub2web",
        description="Convert an EPUB into a complete, browser-optimized static website. "
        "Deterministic: no network calls, no LLM, no prose rewriting.",
        epilog="Example: epub2web book.epub --serve",
    )
    parser.add_argument("epub", type=Path, help="input .epub")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output site directory (default: <title>-site; an existing epub2web site is refreshed)",
    )
    parser.add_argument(
        "--profile",
        choices=("auto", "generic", "doet"),
        default="auto",
        help="extraction profile (default: auto-detect)",
    )
    parser.add_argument("--title", default="", help="override the book title")
    parser.add_argument("--author", default="", help="override the author")
    parser.add_argument(
        "--site-url", default="http://localhost:4321", help="absolute URL used in metadata/sitemap"
    )
    parser.add_argument("--no-search", action="store_true", help="skip the Pagefind index")
    parser.add_argument("--no-verify", action="store_true", help="skip the fidelity gate")
    parser.add_argument("--no-links", action="store_true", help="skip the internal link check")
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing folder even if it was not created by epub2web",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="after a successful build, serve the site locally and open it in a browser",
    )
    parser.add_argument(
        "--port",
        type=_port_number,
        default=DEFAULT_PORT,
        help=f"first local port to try for --serve (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open a browser automatically when using --serve",
    )
    parser.add_argument(
        "--keep-work", action="store_true", help="keep the intermediate content directory"
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
    args = parser.parse_args(argv)

    session = setup_logging(log_dir=args.log_dir, log_file=args.log_file)
    argv_for_log = list(sys.argv if argv is None else [sys.argv[0], *argv])
    log_environment(session, argv=argv_for_log)
    session.context["command"] = argv_for_log
    session.info(
        "command parsed",
        output=str(args.output) if args.output else None,
        profile=args.profile,
        site_url=args.site_url,
        serve=args.serve,
        port=args.port if args.serve else None,
    )

    status = "error"
    exit_code = 2
    try:
        exit_code = _run(args, parser, session)
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
        if exit_code not in (0, 130) and status != "usage":
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
            print(f"Report:  {report}", file=sys.stderr)
            print("         attach this file when reporting the problem", file=sys.stderr)
        elif status != "usage":
            _print_log_path(session)
        session.close()


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser, session: LogSession) -> int:
    started = time.perf_counter()
    epub = args.epub.expanduser().resolve()
    if not epub.exists():
        parser.error(f"no such file: {epub}")

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

    profile = args.profile
    if profile == "auto":
        profile = (
            "doet" if info["doet"] and (ROOT / "scripts" / "extract.py").exists() else "generic"
        )

    slug = slugify(args.title or info["title"] or epub.stem) or "book"
    output = (args.output.expanduser() if args.output else Path.cwd() / f"{slug}-site").resolve()
    if output == Path(output.anchor):
        parser.error("refusing to use a filesystem root as the output folder")

    existing = output.exists()
    cwd = Path.cwd().resolve()
    if existing and (output == cwd or output in cwd.parents):
        parser.error(
            "refusing to replace the current folder or one of its parents; "
            "choose a new subfolder with -o"
        )
    if existing and not args.force:
        if not output.is_dir():
            parser.error(
                f"output path already exists and is not a folder: {output} (use --force to replace it)"
            )
        if not _looks_like_epub2web_site(output):
            try:
                empty = not any(output.iterdir())
            except OSError:
                empty = False
            if not empty:
                parser.error(
                    f"output folder already exists and was not created by epub2web: {output}\n"
                    "Choose a different folder with -o, or pass --force to replace it."
                )

    session.context.update(
        {
            "output": str(output),
            "site_url": args.site_url,
            "profile": profile,
            "refresh": existing,
        }
    )
    session.info(
        "output selected",
        output=str(output),
        profile=profile,
        site_url=args.site_url,
        force=args.force,
        refresh=existing,
    )

    staging = _create_staging(output)
    work = Path(tempfile.mkdtemp(prefix="epub2web-"))
    content = work / "content"
    images = work / "images"
    site_url = args.site_url.rstrip("/")
    session.info("workspace created", work=str(work), staging=str(staging), output=str(output))
    published = False

    try:
        print(f"EPUB:    {info['title'] or epub.name}")
        if info.get("author"):
            print(f"Author:  {info['author']}")
        print(f"Profile: {profile}")
        if existing:
            print("Output:  refreshing the existing site")
        session.info(
            "build started",
            title=info.get("title", ""),
            author=info.get("author", ""),
            profile=profile,
            output=str(output),
            staging=str(staging),
            site_url=site_url,
        )

        if profile == "doet":
            run_doet(epub, content, images, staging, site_url, session)
        else:
            run_generic(epub, content, images, staging, site_url, args.title, args.author)

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
        print(f"Site:    {output / 'index.html'}")

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
                f"Verify:  {'PASS' if verified else 'FAIL'} "
                f"({exact}/{len(result['pages'])} pages exact)"
            )
            if not verified:
                for row in result["pages"]:
                    if row["status"] != "ok":
                        print(
                            f"  ✗ {row['page']}: {row['title']} ({row['source_tokens']} → {row['output_tokens']} tokens)"
                        )
        else:
            print("Verify:  skipped")

        links_ok = True
        if not args.no_links:
            link_result = check_site_links(staging)
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
        if not args.no_search:
            try:
                if run_pagefind(staging, session):
                    search_count = 1
                    print("Search:  Pagefind index built")
                else:
                    print("Search:  skipped (Pagefind not installed; search will be unavailable)")
            except Exception as exc:
                session.exception("pagefind failed", error=str(exc))
                print(f"Search:  skipped (Pagefind failed: {exc})")
        else:
            print("Search:  skipped")
        session.info("search index", built=bool(search_count))

        elapsed = time.perf_counter() - started
        build_ok = verified and links_ok
        summary = {
            "status": "ok" if build_ok else "failed",
            "duration_s": round(elapsed, 3),
            "epub": str(epub),
            "title": info.get("title", ""),
            "author": info.get("author", ""),
            "profile": profile,
            "output": str(output),
            "site_url": site_url,
            "pages": len(book.get("pages", [])),
            "words": stats.get("words", 0),
            "figures": stats.get("figures", 0),
            "images": stats.get("images", 0),
            "verify": {"enabled": not args.no_verify, "pass": verified},
            "links": {"enabled": not args.no_links, "pass": links_ok},
            "search_index": bool(search_count),
        }
        session.write_artifact("summary", summary)

        if not build_ok:
            session.context["error"] = "build rejected by the fidelity or link gate"
            session.error(
                "build rejected by gates",
                fidelity=verified,
                links=links_ok,
                output=str(output),
                staging=str(staging),
            )
            print(f"Time:    {elapsed:.2f}s")
            print()
            print("The build failed its checks, so no preview was started.")
            if existing:
                print(f"Your existing site was left unchanged: {output}")
            else:
                print("No site was published.")
            return 1

        _write_site_marker(staging, info, profile, len(book.get("pages", [])))
        _publish_site(staging, output)
        published = True
        session.info("site published", output=str(output), profile=profile)
        print(f"Time:    {elapsed:.2f}s")

        if args.serve:
            print()
            session.info("preview starting", port=args.port, browser=not args.no_browser)
            exit_code = serve_site(
                output,
                title=info.get("title", "") or epub.stem,
                port=args.port,
                open_browser=not args.no_browser,
            )
            session.info("preview stopped", exit_code=exit_code)
            if exit_code != 0:
                session.context["error"] = "could not start the local preview server"
            return exit_code

        print()
        print("Done. Run the same command with --serve to read it in your browser.")
        session.info("build completed", output=str(output), profile=profile)
        return 0
    finally:
        if not published:
            shutil.rmtree(staging, ignore_errors=True)
        if args.keep_work:
            print(f"Work:    {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
