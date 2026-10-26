"""Remove generated build artefacts. Site outputs are only removed on request."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "build",
    "content",
    "dist",
    "release",
    "public/images",
    "epub2web.egg-info",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
]


def _remove(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    print(f"{'would remove' if dry_run else 'removing'} {path.relative_to(ROOT)}")
    if not dry_run:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove generated artefacts.")
    parser.add_argument("--dry-run", action="store_true", help="show what would be removed")
    parser.add_argument(
        "--sites",
        nargs="*",
        default=[],
        metavar="DIR",
        help="also remove generated site directories",
    )
    args = parser.parse_args(argv)

    for rel in TARGETS:
        _remove(ROOT / rel, args.dry_run)
    for name in args.sites:
        _remove((ROOT / name).resolve(), args.dry_run)
    for cache in ROOT.rglob("__pycache__"):
        _remove(cache, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
