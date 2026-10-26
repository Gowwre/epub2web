"""Keep the packaged generic theme in sync with the site theme."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static"
TARGET = ROOT / "epub2web" / "theme"


def _files(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _source_files() -> dict[str, str]:
    result = _files(SOURCE / "assets")
    favicon = SOURCE / "favicon.svg"
    if favicon.exists():
        result["favicon.svg"] = hashlib.sha256(favicon.read_bytes()).hexdigest()
    return result


def _target_files() -> dict[str, str]:
    result = _files(TARGET / "assets")
    favicon = TARGET / "favicon.svg"
    if favicon.exists():
        result["favicon.svg"] = hashlib.sha256(favicon.read_bytes()).hexdigest()
    return result


def check() -> bool:
    source = _source_files()
    target = _target_files()
    missing = sorted(set(source) - set(target))
    extra = sorted(set(target) - set(source))
    changed = sorted(k for k in source.keys() & target.keys() if source[k] != target[k])
    if not missing and not extra and not changed:
        print("Theme is in sync.")
        return True
    if missing:
        print("Missing from epub2web/theme:", ", ".join(missing))
    if extra:
        print("Unexpected in epub2web/theme:", ", ".join(extra))
    if changed:
        print("Changed in epub2web/theme:", ", ".join(changed))
    return False


def sync() -> None:
    assets = TARGET / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    shutil.copytree(SOURCE / "assets", assets)
    favicon = SOURCE / "favicon.svg"
    if favicon.exists():
        shutil.copyfile(favicon, TARGET / "favicon.svg")
    print(f"Synced {SOURCE} -> {TARGET}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync or check the packaged theme.")
    parser.add_argument("--check", action="store_true", help="fail if the theme is out of sync")
    args = parser.parse_args(argv)
    if args.check:
        return 0 if check() else 1
    sync()
    return 0


if __name__ == "__main__":
    sys.exit(main())
