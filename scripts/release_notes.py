#!/usr/bin/env python3
"""Extract a version's release notes from CHANGELOG.md.

The tag-driven release workflow uses this script so the GitHub release body is
the curated, user-facing changelog section rather than GitHub's commit-derived
"what's changed" list.

Examples:

    python scripts/release_notes.py --version 0.2.0
    python scripts/release_notes.py --version 0.2.0 --output release-notes.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
LINK_RE = re.compile(r"^\[([^\]]+)\]\([^)]*\)")
BRACKET_RE = re.compile(r"^\[([^\]]+)\]")
DATE_SEPARATOR_RE = re.compile(r"\s+[-\u2014\u2013]\s+|\s+\(")


class ReleaseNotesError(ValueError):
    """The requested release section is missing or invalid."""


def _heading_version(line: str) -> str | None:
    """Return the version from a level-2 changelog heading, if it has one."""
    match = HEADING_RE.match(line)
    if match is None:
        return None
    text = match.group(1).strip()

    link = LINK_RE.match(text)
    if link is not None:
        text = link.group(1)
    else:
        bracket = BRACKET_RE.match(text)
        if bracket is not None:
            text = bracket.group(1)

    text = DATE_SEPARATOR_RE.split(text, maxsplit=1)[0].strip()
    if text.lower() == "unreleased":
        return "unreleased"
    return text[1:] if text.startswith(("v", "V")) else text


def extract_release_notes(changelog: str, version: str) -> str:
    """Return the body of the level-2 section for *version*."""
    target = version.strip()
    if target.startswith(("v", "V")):
        target = target[1:]
    if not target:
        raise ReleaseNotesError("version must not be empty")

    found = False
    in_fence = False
    collected: list[str] = []

    for line in changelog.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if found:
                collected.append(line)
            continue

        if not in_fence and line.startswith("## "):
            heading = _heading_version(line)
            if found:
                break
            if heading == target:
                found = True
                continue

        if found:
            collected.append(line)

    if not found:
        raise ReleaseNotesError(f"no '## {target}' section in CHANGELOG.md")

    notes = "\n".join(collected).strip()
    if not notes:
        raise ReleaseNotesError(f"the '## {target}' section in CHANGELOG.md is empty")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a version's notes from CHANGELOG.md.")
    parser.add_argument("--version", required=True, help="version, e.g. 0.2.0")
    parser.add_argument(
        "--changelog",
        default=str(DEFAULT_CHANGELOG),
        help=f"changelog file (default: {DEFAULT_CHANGELOG})",
    )
    parser.add_argument(
        "--output",
        help="write the notes to this file instead of stdout",
    )
    args = parser.parse_args(argv)

    try:
        changelog = Path(args.changelog).read_text(encoding="utf-8")
        notes = extract_release_notes(changelog, args.version)
    except (OSError, ReleaseNotesError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(notes + "\n", encoding="utf-8")
    else:
        print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
