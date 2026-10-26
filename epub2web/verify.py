"""Compare a rendered generic site with its EPUB source text."""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from .text import normalize_text, text_of


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
        lines.append(f"    {tag}: source[{i1}:{i2}]={source[i1:i2][:12]}  output[{j1}:{j2}]={output[j1:j2][:12]}")
        if len(lines) >= 8:
            break
    return "\n".join(lines)


def verify_site(content_dir: str | Path, dist_dir: str | Path, verbose: bool = True) -> dict:
    content_dir = Path(content_dir)
    dist = Path(dist_dir)
    book = json.loads((content_dir / "book.json").read_text(encoding="utf-8"))
    source_text = json.loads((content_dir / "source-text.json").read_text(encoding="utf-8"))
    rows = []
    failures = 0

    for page in book.get("pages", []):
        if page.get("type") == "home" or not page.get("source_files"):
            continue
        path = route_file(dist, page["route"])
        source = normalize_text(" ".join(source_text.get(f, "") for f in page["source_files"]))
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml") if path.exists() else None
        main = soup.find("main") if soup else None
        output = normalize_text(text_of(main)) if main else ""
        src = source.split()
        out = output.split()
        ok = source == output
        if not ok:
            failures += 1
        rows.append({
            "page": page["id"], "title": page.get("title", ""), "status": "ok" if ok else "MISMATCH",
            "source_tokens": len(src), "output_tokens": len(out),
            "detail": "" if ok else first_diff(src, out),
        })

    if verbose:
        print("Generic text fidelity")
        print("=" * 78)
        for row in rows:
            mark = "✓" if row["status"] == "ok" else "✗"
            print(f"  {mark} {row['page']:<10} {row['status']:<9} source {row['source_tokens']:>7,}  output {row['output_tokens']:>7,}  {row['title'][:44]}")
            if row["detail"]:
                print(row["detail"])
        print()
        print(f"Result: {'PASS' if failures == 0 else 'FAIL'} ({failures} page{'s' if failures != 1 else ''})")

    return {"pass": failures == 0, "failures": failures, "pages": rows}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("content")
    parser.add_argument("dist")
    args = parser.parse_args()
    result = verify_site(args.content, args.dist)
    sys.exit(0 if result["pass"] else 1)
