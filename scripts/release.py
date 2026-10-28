#!/usr/bin/env python3
"""Prepare and ship a tagged epub2web release.

Typical flow:

    python scripts/release.py prepare 0.4.0
    # review the diff, run make test, and commit the release prep
    python scripts/release.py ship 0.4.0 --execute

`ship` is a dry run unless `--execute` is supplied. It never publishes to
PyPI directly; pushing the tag lets the Release workflow do the build and
publish steps.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "epub2web" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_RE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
UNRELEASED_RE = re.compile(r"^## Unreleased[ \t]*$", re.MULTILINE)

# `release.py` runs from scripts/, so its sibling module is importable.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from release_notes import ReleaseNotesError, extract_release_notes  # noqa: E402


class ReleaseError(RuntimeError):
    """A release problem that should be reported without a traceback."""


def parse_version(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(value.strip())
    if match is None:
        raise ReleaseError(f"version must look like X.Y.Z: {value!r}")
    return tuple(int(part) for part in match.groups())


def current_version(text: str) -> str:
    match = VERSION_RE.search(text)
    if match is None:
        raise ReleaseError("could not find __version__ in epub2web/__init__.py")
    return match.group(1)


def bump_version(text: str, version: str) -> str:
    if VERSION_RE.search(text) is None:
        raise ReleaseError("could not find __version__ in epub2web/__init__.py")
    return VERSION_RE.sub(f'__version__ = "{version}"', text, count=1)


def prepare_release(
    root: Path,
    version: str,
    release_date: str,
    *,
    dry_run: bool = False,
) -> str:
    """Move Unreleased notes into a dated section and bump the version."""
    new_version = parse_version(version)
    version_path = root / "epub2web" / "__init__.py"
    changelog_path = root / "CHANGELOG.md"
    version_text = version_path.read_text(encoding="utf-8")
    changelog_text = changelog_path.read_text(encoding="utf-8")
    old_version = current_version(version_text)
    if new_version <= parse_version(old_version):
        raise ReleaseError(f"new version {version} must be greater than {old_version}")

    try:
        date.fromisoformat(release_date)
    except ValueError as exc:
        raise ReleaseError(f"invalid release date: {release_date!r}") from exc

    match = UNRELEASED_RE.search(changelog_text)
    if match is None:
        raise ReleaseError("CHANGELOG.md has no '## Unreleased' section")
    body_start = match.end()
    next_heading = re.search(r"^## ", changelog_text[body_start:], re.MULTILINE)
    body_end = body_start + next_heading.start() if next_heading else len(changelog_text)
    body = changelog_text[body_start:body_end].strip()
    if not body:
        raise ReleaseError("CHANGELOG.md has no entries under '## Unreleased'")

    updated_changelog = (
        changelog_text[: match.start()]
        + f"## Unreleased\n\n## {version} - {release_date}"
        + changelog_text[match.end() :]
    )
    try:
        notes = extract_release_notes(updated_changelog, version)
    except ReleaseNotesError as exc:
        raise ReleaseError(str(exc)) from exc

    if not dry_run:
        version_path.write_text(bump_version(version_text, version), encoding="utf-8")
        changelog_path.write_text(updated_changelog, encoding="utf-8")
    return notes


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        errors="replace",
    )


def _git_tag_exists(version: str, *, check_remote: bool) -> bool:
    local = _git("tag", "--list", f"v{version}", check=False)
    if local.stdout.strip():
        return True
    if not check_remote:
        return False
    remote = _git("ls-remote", "--tags", "origin", f"refs/tags/v{version}", check=False)
    return bool(remote.stdout.strip())


def _require_clean_release(version: str, *, check_remote: bool) -> None:
    branch = _git("branch", "--show-current").stdout.strip()
    if branch != "main":
        raise ReleaseError(f"release must run from main, not {branch or 'detached HEAD'}")
    status = _git("status", "--porcelain").stdout.strip()
    if status:
        raise ReleaseError("working tree is not clean; commit the release prep first")
    version_text = (ROOT / "epub2web" / "__init__.py").read_text(encoding="utf-8")
    if current_version(version_text) != version:
        raise ReleaseError(f"epub2web.__version__ does not match {version}")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    try:
        extract_release_notes(changelog, version)
    except ReleaseNotesError as exc:
        raise ReleaseError(str(exc)) from exc
    if _git_tag_exists(version, check_remote=check_remote):
        raise ReleaseError(f"tag v{version} already exists")


def _watch_release(version: str) -> int:
    tag = f"v{version}"
    for _ in range(10):
        result = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "release.yml",
                "--limit",
                "20",
                "--json",
                "databaseId,headBranch",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        if result.returncode == 0:
            try:
                runs = json.loads(result.stdout)
            except json.JSONDecodeError:
                runs = []
            for run in runs:
                if run.get("headBranch") == tag:
                    return subprocess.run(
                        ["gh", "run", "watch", str(run["databaseId"]), "--exit-status"],
                        cwd=ROOT,
                        check=False,
                    ).returncode
        time.sleep(3)
    raise ReleaseError(f"could not find a release workflow run for {tag}")


def ship_release(
    version: str,
    *,
    execute: bool = False,
    skip_checks: bool = False,
    watch: bool = False,
) -> None:
    parse_version(version)
    _require_clean_release(version, check_remote=execute)
    if not skip_checks:
        print("Running tests…", flush=True)
        subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, check=True)

    commands = [
        ["git", "push", "origin", "main"],
        ["git", "tag", f"v{version}"],
        ["git", "push", "origin", f"v{version}"],
    ]
    if not execute:
        print("Dry run; no remote changes made. Pass --execute to ship:")
        for command in commands:
            print("  " + " ".join(command))
        return

    subprocess.run(commands[0], cwd=ROOT, check=True)
    subprocess.run(commands[1], cwd=ROOT, check=True)
    subprocess.run(commands[2], cwd=ROOT, check=True)
    print(f"Tagged v{version}. Release workflow:")
    print("  https://github.com/Gowwre/epub2web/actions/workflows/release.yml")
    if watch and _watch_release(version) != 0:
        raise ReleaseError(f"release workflow for v{version} failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and ship an epub2web release.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser(
        "prepare", help="bump the version and date the Unreleased changelog section"
    )
    prepare.add_argument("version", help="release version, e.g. 0.4.0")
    prepare.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="release date in YYYY-MM-DD form (default: today)",
    )
    prepare.add_argument("--dry-run", action="store_true", help="show what would change")

    ship = subparsers.add_parser("ship", help="push main and the release tag")
    ship.add_argument("version", help="release version, e.g. 0.4.0")
    ship.add_argument("--execute", action="store_true", help="actually push the tag")
    ship.add_argument("--skip-checks", action="store_true", help="skip the local test run")
    ship.add_argument("--watch", action="store_true", help="watch the release workflow")

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            notes = prepare_release(ROOT, args.version, args.date, dry_run=args.dry_run)
            action = "Would prepare" if args.dry_run else "Prepared"
            print(f"{action} {args.version}.")
            print(notes)
            if not args.dry_run:
                print("\nNext: review the diff, run `make test`, commit, then:")
                print(f"  make release-ship VERSION={args.version}")
        else:
            ship_release(
                args.version,
                execute=args.execute,
                skip_checks=args.skip_checks,
                watch=args.watch,
            )
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        command = " ".join(str(part) for part in exc.cmd)
        print(f"error: command failed with exit code {exc.returncode}: {command}", file=sys.stderr)
        return exc.returncode or 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
