#!/usr/bin/env python3
"""Build self-contained desktop GUI bundles for epub2web.

PyInstaller is not a cross-compiler: run this script on the operating system
you want to target. It creates the friendliest artifact for that platform:

* Windows: a single ``.exe`` that can be double-clicked.
* macOS: a ``.dmg`` with the ``.app`` bundle and an Applications shortcut.
* Linux: an ``.AppImage`` when ``appimagetool`` is available, otherwise a
  portable ``.tar.gz`` containing the application folder.

The bundled executable includes Python, Tk, the templates, the theme, and the
fonts. Users do not need Python or any packages installed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "epub2web-gui"
APP_TITLE = "epub2web"
BUNDLE_ID = "io.github.gowwre.epub2web"
DEFAULT_OUTPUT = ROOT / "dist" / "portable"
BUILD_ROOT = ROOT / "build" / "portable"
ENTRY_POINT = ROOT / "scripts" / "gui_entry.py"
ICON_SOURCE = ROOT / "epub2web" / "theme" / "gui-icon.png"
LICENSE_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md")
BUNDLED_DISTRIBUTIONS = (
    "beautifulsoup4",
    "Jinja2",
    "lxml",
    "Pillow",
    "soupsieve",
    "MarkupSafe",
    "typing_extensions",
    "pyinstaller",
)
LICENSE_NAMES = {
    "license",
    "license.md",
    "license.rst",
    "license.txt",
    "license.terms",
    "licenses",
    "licenses.md",
    "licenses.txt",
    "copying",
    "copying.rst",
    "copying.txt",
    "notice",
    "notice.txt",
    "notices",
    "notices.txt",
    "copyright",
}


class BuildError(RuntimeError):
    """A packaging problem that should be reported without a traceback."""


def project_version() -> str:
    """Read the version without importing the package and its dependencies."""
    text = (ROOT / "epub2web" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise BuildError("could not find __version__ in epub2web/__init__.py")
    return match.group(1)


def platform_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    raise BuildError(f"unsupported build platform: {sys.platform}")


def arch_name(name: str | None = None) -> str:
    name = name or platform_name()
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x64" if name in {"windows", "macos"} else "x86_64"
    if machine in {"arm64", "aarch64"}:
        return "arm64" if name == "macos" else "aarch64"
    if machine in {"x86", "i386", "i686"}:
        return "x86"
    if machine in {"armv7l", "armv7"}:
        return "armv7l"
    raise BuildError(f"unsupported build architecture: {platform.machine()}")


def appimage_arch(name: str) -> str:
    return {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
        "armv7l": "armhf",
    }.get(name, name)


def artifact_stem(version: str, name: str | None = None, arch: str | None = None) -> str:
    return f"{APP_NAME}-{version}-{name or platform_name()}-{arch or arch_name(name)}"


def pyinstaller_command(
    stage: Path,
    *,
    one_file: bool,
    icon: Path | None,
    name: str | None = None,
) -> list[str]:
    """Return the PyInstaller command for the current platform."""
    name = name or platform_name()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--paths",
        str(ROOT),
        "--collect-data",
        "epub2web",
        "--collect-submodules",
        "epub2web",
        "--distpath",
        str(stage / "pyinstaller-dist"),
        "--workpath",
        str(stage / "pyinstaller-work"),
        "--specpath",
        str(stage / "pyinstaller-spec"),
    ]
    if one_file:
        command.append("--onefile")
    if name in {"windows", "macos"}:
        command.append("--windowed")
    if icon is not None:
        command.extend(["--icon", str(icon)])
    if name == "macos":
        command.extend(["--osx-bundle-identifier", BUNDLE_ID])
    command.append(str(ENTRY_POINT))
    return command


def _ensure_build_dependencies() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise BuildError(
            "PyInstaller is not installed. Run: pip install -e '.[gui-build]'"
        ) from exc
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        raise BuildError(
            "Tkinter is not available in this Python. Install the Tk package for "
            "your distribution, then try again."
        ) from exc


def _make_icon(stage: Path) -> Path | None:
    if sys.platform not in {"win32", "darwin"}:
        return None
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a project dependency
        raise BuildError("Pillow is required to generate the application icon.") from exc
    if not ICON_SOURCE.is_file():
        raise BuildError(f"application icon not found: {ICON_SOURCE}")

    image = Image.open(ICON_SOURCE).convert("RGBA")
    if sys.platform == "win32":
        target = stage / f"{APP_NAME}.ico"
        image.resize((256, 256), Image.Resampling.LANCZOS).save(
            target,
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    else:
        target = stage / f"{APP_NAME}.icns"
        image.resize((1024, 1024), Image.Resampling.LANCZOS).save(target)
    return target


def _built_path(stage: Path, one_file: bool, name: str) -> Path:
    dist = stage / "pyinstaller-dist"
    if name == "macos":
        return dist / f"{APP_NAME}.app"
    if one_file:
        return dist / f"{APP_NAME}.exe" if name == "windows" else dist / APP_NAME
    return dist / APP_NAME


def _frozen_executable(built: Path, one_file: bool, name: str) -> Path:
    if name == "macos":
        return built / "Contents" / "MacOS" / APP_NAME
    if one_file:
        return built
    if name == "windows":
        return built / f"{APP_NAME}.exe"
    return built / APP_NAME


def _write_smoke_epub(path: Path) -> None:
    """Create a tiny valid EPUB so the frozen build exercises real resources."""
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Portable Smoke Test</dc:title>
    <dc:creator>epub2web</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="id">urn:uuid:epub2web-portable-smoke</dc:identifier>
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="ch1"/>
  </spine>
</package>
"""
    chapter = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>Chapter One</title></head>
<body><h1>Chapter One</h1><p>Hello portable world.</p></body>
</html>
"""
    with zipfile.ZipFile(path, "w") as archive:
        mimetype = zipfile.ZipInfo("mimetype")
        mimetype.compress_type = zipfile.ZIP_STORED
        archive.writestr(mimetype, "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", opf)
        archive.writestr("OEBPS/ch1.xhtml", chapter)


def _smoke_test(executable: Path, stage: Path) -> None:
    """Check Tk imports and run a real conversion through the frozen worker."""
    check = subprocess.run(
        [str(executable), "--self-test"],
        cwd=str(stage),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=120,
        check=False,
    )
    if check.returncode != 0:
        details = (check.stdout + check.stderr).strip()
        raise BuildError(f"frozen GUI cannot import Tk (exit {check.returncode}): {details}")

    epub = stage / "smoke.epub"
    site = stage / "smoke-site"
    _write_smoke_epub(epub)
    result = subprocess.run(
        [
            str(executable),
            "--worker",
            str(epub),
            "-o",
            str(site),
            "--log-dir",
            str(stage / "smoke-logs"),
            "--report-dir",
            str(stage / "smoke-reports"),
        ],
        cwd=str(stage),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stdout + result.stderr).strip()
        raise BuildError(
            f"frozen worker failed its smoke conversion (exit {result.returncode}): {details}"
        )
    if not (site / "index.html").is_file():
        raise BuildError("frozen worker completed but did not produce site/index.html")


def _license_files_in(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    for child in children:
        if child.is_file() and child.name.lower() in LICENSE_NAMES:
            found.append(child)
        elif child.is_dir() and child.name.lower().startswith(("tcl", "tk", "python")):
            try:
                grandchildren = list(child.iterdir())
            except OSError:
                continue
            for grandchild in grandchildren:
                if grandchild.is_file() and grandchild.name.lower() in LICENSE_NAMES:
                    found.append(grandchild)
    return found


def _collect_license_texts() -> list[tuple[str, str]]:
    """Collect license texts for the runtime that PyInstaller will bundle."""
    texts: list[tuple[str, str]] = []
    seen: set[str] = set()
    tcl_tk_found = False

    def add(label: str, path: Path) -> None:
        nonlocal tcl_tk_found
        try:
            body = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return
        if not body:
            return
        if "tcl/tk" in label.lower():
            tcl_tk_found = True
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if digest in seen:
            return
        seen.add(digest)
        texts.append((label, body))

    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    python_licenses = [
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
        Path(sys.base_prefix) / "Resources" / "LICENSE.txt",
        Path(sys.base_prefix) / "lib" / f"python{version}" / "LICENSE.txt",
        Path("/usr/share/doc") / f"python{version}" / "copyright",
    ]
    for path in python_licenses:
        if path.is_file():
            add(f"Python ({path.name})", path)
            break

    for dist_name in BUNDLED_DISTRIBUTIONS:
        try:
            dist = distribution(dist_name)
        except PackageNotFoundError:
            continue
        for entry in dist.files or []:
            if entry.name.lower() not in LICENSE_NAMES:
                continue
            path = Path(dist.locate_file(entry))
            if path.is_file():
                add(f"{dist_name} ({entry.name})", path)

    roots = [
        Path(sys.base_prefix) / "tcl",
        Path(sys.base_prefix) / "lib",
        Path("/usr/share/licenses/tcl"),
        Path("/usr/share/licenses/tk"),
        Path("/Library/Frameworks/Tcl.framework/Resources"),
        Path("/Library/Frameworks/Tk.framework/Resources"),
    ]
    for pattern in ("tcl*", "tk*"):
        roots.extend(Path("/usr/share/doc").glob(pattern))
    seen_paths: set[Path] = set()
    for root in roots:
        for path in _license_files_in(root):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            add(f"Tcl/Tk ({path.parent.name}/{path.name})", path)

    if not tcl_tk_found:
        print(
            "warning: Tcl/Tk license files were not found in this build environment; "
            "THIRD_PARTY_NOTICES.md links to the license.",
            file=sys.stderr,
        )
    return texts


def _write_license_bundle(
    out_dir: Path, name: str, arch: str, texts: list[tuple[str, str]]
) -> Path:
    for filename in LICENSE_FILES:
        source = ROOT / filename
        target = out_dir / filename
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    path = out_dir / f"THIRD_PARTY_LICENSES-{name}-{arch}.txt"
    lines = [
        f"epub2web third-party license texts ({name}-{arch})",
        "",
        "See THIRD_PARTY_NOTICES.md for attribution and license summaries.",
        "",
    ]
    for label, body in texts:
        lines.extend(["=" * 78, label, "=" * 78, "", body, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _copy_license_files(destination: Path, license_bundle: Path) -> None:
    for filename in LICENSE_FILES:
        shutil.copy2(ROOT / filename, destination / filename)
    shutil.copy2(license_bundle, destination / license_bundle.name)


def _portable_readme(version: str, name: str, arch: str) -> str:
    if name == "windows":
        run = (
            "Double-click epub2web-gui-*.exe. Windows SmartScreen may warn because\n"
            "this build is not code-signed yet: choose More info, then Run anyway.\n"
        )
    elif name == "macos":
        run = (
            "Open the .dmg (or unzip the .zip) and drag epub2web-gui.app to\n"
            "Applications. Because the build is not notarized yet, macOS may\n"
            "block the first launch: right-click the app, choose Open, then\n"
            "confirm. Or run:\n"
            "  xattr -dr com.apple.quarantine /Applications/epub2web-gui.app\n"
        )
    else:
        run = (
            "Run the .AppImage directly (chmod +x if needed). If FUSE is missing,\n"
            "use: ./epub2web-gui-*.AppImage --appimage-extract-and-run\n"
            "For the .tar.gz fallback, extract it and run ./epub2web-gui/epub2web-gui.\n"
        )

    return f"""epub2web {version} - portable desktop GUI ({name}-{arch})

This build contains Python, Tk, and everything epub2web needs. You do not
need to install Python or any packages.

How to run
----------
{run}
The GUI asks for an EPUB, converts it, and opens the result in your browser.
Book sites are written to Documents/epub2web/<book>-site (or
~/epub2web/<book>-site when there is no Documents folder).

Data and logs
-------------
Linux:   ~/.local/share/epub2web
macOS:   ~/Library/Application Support/epub2web
Windows: %LOCALAPPDATA%\\epub2web

The portable build does not store anything beside the executable; removing
the downloaded file or app folder leaves your books and logs intact.

License notices are in LICENSE, THIRD_PARTY_NOTICES.md, and
THIRD_PARTY_LICENSES-{name}-{arch}.txt.

The command-line edition is still available separately with pip:
  pip install epub2web
  epub2web book.epub --serve
"""


def _write_readme(out_dir: Path, version: str, name: str, arch: str) -> Path:
    path = out_dir / f"README-{name}-{arch}.txt"
    path.write_text(_portable_readme(version, name, arch), encoding="utf-8")
    return path


def _stage_package(source: Path, stage: Path, readme: str, name: str, license_bundle: Path) -> Path:
    package = stage / "package" / APP_NAME
    package.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, package, symlinks=True)
    else:
        package.mkdir(parents=True)
        target = package / (f"{APP_NAME}.exe" if name == "windows" else APP_NAME)
        shutil.copy2(source, target)
        target.chmod(target.stat().st_mode | 0o111)
    (package / "README.txt").write_text(readme, encoding="utf-8", newline="\n")
    _copy_license_files(package, license_bundle)
    return package


def _make_zip(package: Path, stem: Path) -> Path:
    archive = shutil.make_archive(
        str(stem), "zip", root_dir=str(package.parent), base_dir=package.name
    )
    return Path(archive)


def _make_tarball(package: Path, stem: Path) -> Path:
    archive = shutil.make_archive(
        str(stem), "gztar", root_dir=str(package.parent), base_dir=package.name
    )
    return Path(archive)


def _make_appimage(
    built: Path,
    tool: Path,
    out_dir: Path,
    stem: str,
    stage: Path,
    arch: str,
    license_bundle: Path,
) -> Path:
    appdir = stage / "AppDir"
    appdir.mkdir(parents=True)
    if built.is_dir():
        shutil.copytree(built, appdir, dirs_exist_ok=True, symlinks=True)
    else:
        target = appdir / APP_NAME
        shutil.copy2(built, target)
        target.chmod(target.stat().st_mode | 0o111)

    icon = appdir / f"{APP_NAME}.png"
    shutil.copy2(ICON_SOURCE, icon)
    icon_dir = appdir / "usr" / "share" / "icons" / "hicolor" / "128x128" / "apps"
    icon_dir.mkdir(parents=True)
    shutil.copy2(ICON_SOURCE, icon_dir / f"{APP_NAME}.png")

    apprun = appdir / "AppRun"
    apprun.write_text(
        '#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/epub2web-gui" "$@"\n',
        encoding="utf-8",
    )
    apprun.chmod(0o755)

    (appdir / f"{APP_NAME}.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_TITLE}\n"
        "Comment=Turn an EPUB into a website\n"
        f"Exec={APP_NAME}\n"
        f"Icon={APP_NAME}\n"
        "Terminal=false\n"
        "Categories=Office;Publishing;\n"
        f"StartupWMClass={APP_NAME}\n",
        encoding="utf-8",
    )
    _copy_license_files(appdir, license_bundle)

    output = out_dir / f"{stem}.AppImage"
    if output.exists():
        output.unlink()
    environment = os.environ.copy()
    environment["ARCH"] = appimage_arch(arch)
    environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    subprocess.run(
        [str(tool), "--no-appstream", str(appdir), str(output)],
        cwd=str(stage),
        env=environment,
        check=True,
    )
    return output


def _make_dmg(
    app: Path, out_dir: Path, stem: str, stage: Path, readme: str, license_bundle: Path
) -> Path:
    output = out_dir / f"{stem}.dmg"
    hdiutil = shutil.which("hdiutil")
    if hdiutil is not None:
        payload = stage / "dmg"
        payload.mkdir(parents=True)
        shutil.copytree(app, payload / app.name, symlinks=True)
        (payload / "README.txt").write_text(readme, encoding="utf-8", newline="\n")
        _copy_license_files(payload, license_bundle)
        (payload / "Applications").symlink_to("/Applications")
        if output.exists():
            output.unlink()
        try:
            subprocess.run(
                [
                    hdiutil,
                    "create",
                    "-volname",
                    APP_TITLE,
                    "-srcfolder",
                    str(payload),
                    "-ov",
                    "-format",
                    "UDZO",
                    str(output),
                ],
                check=True,
            )
            return output
        except subprocess.CalledProcessError:
            print("warning: hdiutil failed; falling back to a zip archive", file=sys.stderr)
            if output.exists():
                output.unlink()

    archive = out_dir / f"{stem}.zip"
    ditto = shutil.which("ditto")
    if ditto is not None:
        subprocess.run(
            [
                ditto,
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(app),
                str(archive),
            ],
            check=True,
        )
    else:
        archive = Path(
            shutil.make_archive(
                str(out_dir / stem), "zip", root_dir=str(app.parent), base_dir=app.name
            )
        )
    return archive


def _package(
    built: Path,
    *,
    one_file: bool,
    version: str,
    name: str,
    arch: str,
    stage: Path,
    out_dir: Path,
    appimage_tool: Path | None,
    license_bundle: Path,
) -> Path:
    stem = artifact_stem(version, name, arch)
    readme_path = _write_readme(out_dir, version, name, arch)
    readme = readme_path.read_text(encoding="utf-8")

    if name == "windows":
        if one_file:
            target = out_dir / f"{stem}.exe"
            shutil.copy2(built, target)
            return target
        package = _stage_package(built, stage, readme, name, license_bundle)
        return _make_zip(package, out_dir / stem)

    if name == "macos":
        return _make_dmg(built, out_dir, stem, stage, readme, license_bundle)

    if appimage_tool is not None:
        return _make_appimage(built, appimage_tool, out_dir, stem, stage, arch, license_bundle)

    package = _stage_package(built, stage, readme, name, license_bundle)
    return _make_tarball(package, out_dir / stem)


def resolve_appimagetool(explicit: str | None) -> Path | None:
    candidates: list[Path] = []
    env_value = os.environ.get("APPIMAGETOOL")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if env_value:
        candidates.append(Path(env_value).expanduser())
    found = shutil.which("appimagetool")
    if found:
        candidates.append(Path(found))

    for candidate in candidates:
        if candidate.is_file():
            if os.name != "nt" and not os.access(candidate, os.X_OK):
                raise BuildError(f"appimagetool is not executable: {candidate}")
            return candidate.resolve()
    if explicit or env_value:
        raise BuildError(f"appimagetool not found: {explicit or env_value}")
    return None


def _checksum(path: Path) -> Path:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    target = path.with_name(path.name + ".sha256")
    target.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return target


def _verify_appimage(path: Path) -> None:
    """Run the finished AppImage once to validate the wrapper, not just the payload."""
    environment = os.environ.copy()
    environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    result = subprocess.run(
        [str(path), "--self-test"],
        env=environment,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stdout + result.stderr).strip()
        raise BuildError(
            f"packaged AppImage failed its smoke test (exit {result.returncode}): {details}"
        )


def build(args: argparse.Namespace) -> int:
    name = platform_name()
    arch = arch_name(name)
    version = project_version()
    out_dir = Path(args.output_dir).expanduser().resolve()
    one_file = args.one_file if args.one_file is not None else name == "windows"

    _ensure_build_dependencies()

    appimage_tool: Path | None = None
    if name == "linux" and not args.no_appimage:
        appimage_tool = resolve_appimagetool(args.appimage_tool)

    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    BUILD_ROOT.mkdir(parents=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    license_bundle = _write_license_bundle(out_dir, name, arch, _collect_license_texts())

    icon = _make_icon(BUILD_ROOT)
    command = pyinstaller_command(BUILD_ROOT, one_file=one_file, icon=icon, name=name)
    print(f"Building {APP_NAME} {version} for {name}-{arch}...", flush=True)
    subprocess.run(command, cwd=str(ROOT), check=True)

    built = _built_path(BUILD_ROOT, one_file, name)
    executable = _frozen_executable(built, one_file, name)
    print("Running packaged smoke test...", flush=True)
    _smoke_test(executable, BUILD_ROOT)

    artifact = _package(
        built,
        one_file=one_file,
        version=version,
        name=name,
        arch=arch,
        stage=BUILD_ROOT,
        out_dir=out_dir,
        appimage_tool=appimage_tool,
        license_bundle=license_bundle,
    )
    if artifact.suffix == ".AppImage":
        print("Verifying AppImage wrapper...", flush=True)
        _verify_appimage(artifact)
    checksum = _checksum(artifact)

    size_mb = artifact.stat().st_size / (1024 * 1024)
    print(f"Built:    {artifact}")
    print(f"Size:     {size_mb:.1f} MB")
    print(f"Checksum: {checksum}")
    if name == "linux" and appimage_tool is None and not args.no_appimage:
        print(
            "note: appimagetool was not found, so a tar.gz was built instead. "
            "Set APPIMAGETOOL or --appimage-tool to create an AppImage."
        )

    if not args.keep_work:
        shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a portable desktop GUI for the current platform."
    )
    style = parser.add_mutually_exclusive_group()
    style.add_argument(
        "--onefile",
        dest="one_file",
        action="store_true",
        help="package the application as a single executable",
    )
    style.add_argument(
        "--onedir",
        dest="one_file",
        action="store_false",
        help="package the application as a folder",
    )
    parser.set_defaults(one_file=None)
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT),
        help=f"where to write artifacts (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--no-appimage",
        action="store_true",
        help="on Linux, skip AppImage and build a tar.gz even when appimagetool is available",
    )
    parser.add_argument(
        "--appimage-tool",
        metavar="PATH",
        help="path to appimagetool (or set APPIMAGETOOL)",
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="keep build/portable for inspection after a successful build",
    )
    args = parser.parse_args(argv)

    try:
        return build(args)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        command = " ".join(str(part) for part in exc.cmd)
        print(f"error: command failed with exit code {exc.returncode}: {command}", file=sys.stderr)
        return exc.returncode or 2
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
