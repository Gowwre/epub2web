"""Text and structure fidelity gates for a rendered book site.

The text gate compares every built page inside <main> with the corresponding
EPUB source, token-for-token. Structural checks currently cover the cover.
Generated chrome is excluded through data-chrome / data-generated.
"""

from __future__ import annotations

import difflib
import json
import logging
from pathlib import Path

from bs4 import BeautifulSoup

from .paths import route_to_file
from .progress import ProgressCallback
from .progress import report as report_progress
from .text import normalize_text, text_of

logger = logging.getLogger(__name__)


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


def _structural_checks(book: dict, dist: Path) -> dict:
    checks: dict[str, dict] = {}
    cover = book.get("meta", {}).get("cover", "")
    if cover:
        cover_path = dist / "images" / cover
        checks["cover"] = {"expected": 1, "actual": 1 if cover_path.exists() else 0}
    return checks


def verify_site(
    content_dir: str | Path,
    dist_dir: str | Path,
    verbose: bool = True,
    progress: ProgressCallback | None = None,
) -> dict:
    content_dir = Path(content_dir)
    dist = Path(dist_dir)
    book = json.loads((content_dir / "book.json").read_text(encoding="utf-8"))
    source_text = json.loads((content_dir / "source-text.json").read_text(encoding="utf-8"))

    rows: list[dict] = []
    failures = 0
    pages = book.get("pages", [])
    total_pages = len(pages)
    report_progress(progress, "verify", "Checking every word", 0, total_pages)

    for page_index, page in enumerate(pages, 1):
        if page.get("type") == "home" or not page.get("source_files"):
            report_progress(progress, "verify", "Checking every word", page_index, total_pages)
            continue
        path = route_to_file(dist, page["route"])
        source = source_text.get(page["id"])
        if source is None:
            source = normalize_text(" ".join(source_text.get(f, "") for f in page["source_files"]))
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml") if path.exists() else None
        main = soup.find("main") if soup else None
        output = normalize_text(text_of(main)) if main else ""
        src_tokens = source.split()
        out_tokens = output.split()
        text_ok = src_tokens == out_tokens
        expected_images = int(page.get("images", 0) or 0)
        actual_images = len(main.find_all("img")) if main else 0
        images_ok = expected_images == actual_images
        ok = text_ok and images_ok
        if not ok:
            failures += 1
        if text_ok and images_ok:
            status = "ok"
        elif not text_ok:
            status = "TEXT+IMAGE MISMATCH" if not images_ok else "TEXT MISMATCH"
        else:
            status = "IMAGE MISMATCH"
        detail = first_diff(src_tokens, out_tokens) if not text_ok else ""
        if not images_ok:
            detail += (
                f"\n    images: source {expected_images:,} / output {actual_images:,}"
            ).rstrip()
        rows.append(
            {
                "page": page["id"],
                "title": page.get("title", ""),
                "status": status,
                "source_tokens": len(src_tokens),
                "output_tokens": len(out_tokens),
                "source_images": expected_images,
                "output_images": actual_images,
                "detail": detail.strip(),
            }
        )
        report_progress(progress, "verify", "Checking every word", page_index, total_pages)

    checks = _structural_checks(book, dist)
    for result in checks.values():
        if result["expected"] != result["actual"]:
            failures += 1

    for row in rows:
        if row["status"] != "ok":
            logger.info(
                "fidelity mismatch",
                extra={
                    "page": row["page"],
                    "status": row["status"],
                    "source_tokens": row["source_tokens"],
                    "output_tokens": row["output_tokens"],
                    "detail": row["detail"],
                },
            )
    for key, result in checks.items():
        if result["expected"] != result["actual"]:
            logger.info("structural mismatch", extra={"check": key, **result})

    report = {
        "pass": failures == 0,
        "failures": failures,
        "pages": rows,
        "checks": checks,
    }
    logger.info(
        "fidelity gate",
        extra={
            "status": "pass" if failures == 0 else "fail",
            "pages": len(rows),
            "failures": failures,
        },
    )
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
