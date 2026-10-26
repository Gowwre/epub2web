"""Text and structure fidelity gates for a rendered book site.

The text gate compares every built page inside <main> with the corresponding
EPUB source, token-for-token and character-for-character. Structural checks
cover notes, references, index entries, and the cover. Generated chrome is
excluded through data-chrome / data-generated.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from .text import normalize_text, text_of

ROOT = Path(__file__).resolve().parents[1]


def route_file(dist: Path, route: str) -> Path:
    if route == "/":
        return dist / "index.html"
    return dist / route.strip("/") / "index.html"


def first_diff(source: list[str], output: list[str]) -> str:
    matcher = difflib.SequenceMatcher(a=source, b=output, autojunk=False)
    lines = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        lines.append(
            f"    {tag}: source[{i1}:{i2}]={source[i1:i2][:12]}  "
            f"output[{j1}:{j2}]={output[j1:j2][:12]}"
        )
        if len(lines) >= 8:
            break
    return "\n".join(lines)


def _find_page(pages: list[dict], key: str) -> dict | None:
    return next((p for p in pages if p.get("id") == key), None) or next(
        (p for p in pages if key in p.get("title", "").lower()), None
    )


def _count(dist: Path, page: dict | None, selector: str) -> int:
    if page is None:
        return 0
    path = route_file(dist, page["route"])
    if not path.exists():
        return 0
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    return len(soup.select(selector))


def _structural_checks(book: dict, dist: Path) -> dict:
    pages = book.get("pages", [])
    stats = book.get("stats", {})
    checks: dict[str, dict] = {}

    for key, selector in (
        ("notes", "article.note"),
        ("references", ".reference-list > li"),
        ("index_entries", "[data-index-text]"),
    ):
        expected = stats.get(key, 0)
        if not expected:
            continue
        lookup = "index" if key == "index_entries" else key
        page = _find_page(pages, lookup)
        if page is None:
            continue
        actual = _count(dist, page, selector)
        checks[key] = {"expected": expected, "actual": actual}

    cover = book.get("meta", {}).get("cover", "")
    cover_path = dist / "images" / (cover or "cover.jpg")
    if cover or cover_path.exists():
        checks["cover"] = {"expected": 1, "actual": 1 if cover_path.exists() else 0}

    return checks


def verify_site(
    content_dir: str | Path,
    dist_dir: str | Path,
    verbose: bool = True,
) -> dict:
    content_dir = Path(content_dir)
    dist = Path(dist_dir)
    book = json.loads((content_dir / "book.json").read_text(encoding="utf-8"))
    source_text = json.loads((content_dir / "source-text.json").read_text(encoding="utf-8"))

    rows: list[dict] = []
    failures = 0

    for page in book.get("pages", []):
        if page.get("type") == "home" or not page.get("source_files"):
            continue
        path = route_file(dist, page["route"])
        source = normalize_text(" ".join(source_text.get(f, "") for f in page["source_files"]))
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml") if path.exists() else None
        main = soup.find("main") if soup else None
        output = normalize_text(text_of(main)) if main else ""
        src_tokens = source.split()
        out_tokens = output.split()
        token_ok = src_tokens == out_tokens
        char_ok = source == output
        ok = token_ok and char_ok
        status = "ok" if ok else ("MISMATCH" if not token_ok else "CHAR MISMATCH")
        if not ok:
            failures += 1
            if token_ok:
                matcher = difflib.SequenceMatcher(a=source, b=output, autojunk=False)
                detail = "    character-level difference: " + repr(matcher.get_opcodes()[:5])
            else:
                detail = first_diff(src_tokens, out_tokens)
        else:
            detail = ""
        rows.append(
            {
                "page": page["id"],
                "title": page.get("title", ""),
                "status": status,
                "source_tokens": len(src_tokens),
                "output_tokens": len(out_tokens),
                "detail": detail,
            }
        )

    checks = _structural_checks(book, dist)
    for result in checks.values():
        if result["expected"] != result["actual"]:
            failures += 1

    report = {
        "pass": failures == 0,
        "failures": failures,
        "pages": rows,
        "checks": checks,
    }
    report_path = content_dir / "fidelity-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if verbose:
        print("Text fidelity")
        print("=" * 78)
        for row in rows:
            mark = "✓" if row["status"] == "ok" else "✗"
            print(
                f"  {mark} {row['page']:<18} {row['status']:<13} "
                f"source {row['source_tokens']:>7,}  output {row['output_tokens']:>7,}"
            )
            if row["detail"]:
                print(row["detail"])
        if checks:
            print()
            print("Structural checks")
            print("=" * 78)
            for key, result in checks.items():
                mark = "✓" if result["expected"] == result["actual"] else "✗"
                print(
                    f"  {mark} {key:<14} expected {result['expected']:>7,}  "
                    f"actual {result['actual']:>7,}"
                )
        total_source = sum(row["source_tokens"] for row in rows)
        total_output = sum(row["output_tokens"] for row in rows)
        print()
        print(f"Total compared tokens: source {total_source:,} / output {total_output:,}")
        print(
            f"Result: {'PASS' if failures == 0 else 'FAIL'} ({failures} failure{'s' if failures != 1 else ''})"
        )

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify text and structure fidelity.")
    parser.add_argument(
        "content", nargs="?", default=os.environ.get("CONTENT_DIR", str(ROOT / "content"))
    )
    parser.add_argument("dist", nargs="?", default=os.environ.get("DIST_DIR", str(ROOT / "dist")))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    report = verify_site(args.content, args.dist, verbose=not args.quiet)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
