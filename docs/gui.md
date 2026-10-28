# Desktop GUI

The repository includes a small cross-platform Tkinter front end:

```bash
pip install -e .
epub2web-gui
```

Choose a reflowable EPUB 2/3 file and click **Convert**. The site is built with
the same extractor, fidelity gate, link gate, and theme as the CLI, then opens
in the default browser.

- Output defaults to `~/Documents/epub2web/<book>-site`, or
  `~/epub2web/<book>-site` when there is no `Documents` folder.
- The local preview server stays alive while you browse, so navigation and
  search work. **Stop** shuts it down; closing the window also stops it.
- Logs go to the platform application-data directory (`~/.local/share/epub2web`
  on Linux, `~/Library/Application Support/epub2web` on macOS, and
  `%LOCALAPPDATA%\epub2web` on Windows). Failure support ZIPs are written to
  the `reports` subdirectory.
- The GUI is a thin front end. For automation, use the CLI.

## Requirements

Tkinter is part of the Python standard library, but some Linux distributions
package it separately:

```bash
sudo apt install python3-tk
```

Windows and macOS installers from [python.org](https://www.python.org/) include
Tk. If Tk is missing, the GUI prints installation instructions and the CLI
continues to work normally.

## Architecture

- `epub2web/gui.py` — launcher and hidden `--worker` routing.
- `epub2web/tk_app.py` — Tkinter view. All widget calls stay on the Tk thread.
- `epub2web/controller.py` — toolkit-independent process controller. It streams
  events from the worker and never imports Tk.
- `epub2web/worker.py` — worker process that calls the existing CLI.
- `epub2web/progress.py` — phase progress definitions and the machine-readable
  `--progress` stream used by the worker.
- `scripts/build_gui.py` — portable bundle builder for Windows, macOS, and Linux.
- `scripts/gui_entry.py` — PyInstaller entry point.

The view sends user actions to `BuildController`; the controller spawns a
worker and emits `BuildEvent` objects. The Tk app puts those events on a queue
and applies them on the Tk main thread. Replacing Tkinter with Qt or a local web
view should not require changes to the controller or worker.

Progress is reported for reading, per-image optimization, page conversion,
rendering, fidelity verification, link checking, and publishing. The GUI turns
those events into a determinate progress bar, a live stage counter, and
milestone log lines.

## Portable builds

`make gui-portable` creates a self-contained build for the current platform.
The result includes Python, Tk, the templates, the theme, and the fonts, so
users do not install Python or any packages. PyInstaller is not a
cross-compiler: run the build on each target operating system.

```bash
pip install -e ".[gui-build]"
make gui-portable
```

Run these commands inside the project virtual environment so PyInstaller and
the application dependencies use the same interpreter.

The script chooses the friendliest format for the platform:

| Platform | Default artifact | Notes |
|---|---|---|
| Windows | `epub2web-gui-<version>-windows-x64.exe` | One file; double-click. |
| macOS | `epub2web-gui-<version>-macos-<arch>.dmg` | Contains the `.app` and an Applications shortcut. |
| Linux | `epub2web-gui-<version>-linux-<arch>.AppImage` | Falls back to `.tar.gz` when `appimagetool` is unavailable. |

Every artifact is written to `dist/portable/`, together with a platform-specific
`README-*.txt`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, a generated
`THIRD_PARTY_LICENSES-*.txt` for Python/Tcl/Tk and bundled dependencies, and a
`.sha256` checksum. Options:

| Option | Meaning |
|---|---|
| `--onefile` / `--onedir` | Force a single executable or a folder. Windows defaults to `--onefile`; macOS and Linux default to `--onedir`. |
| `--output-dir DIR` | Write artifacts somewhere other than `dist/portable`. |
| `--no-appimage` | On Linux, build the `.tar.gz` even if `appimagetool` is available. |
| `--appimage-tool PATH` | Point at `appimagetool`; `APPIMAGETOOL` works too. |
| `--keep-work` | Keep `build/portable/` for inspection after a successful build. |

The build command uses `--collect-data epub2web` for templates, CSS, JavaScript,
and fonts, and `--collect-submodules epub2web` so the hidden `--worker` mode and
Tk modules survive freezing. Before packaging, it runs two smoke tests against
the frozen executable: `--self-test` confirms Tk can be imported, then a
generated one-page EPUB is converted through the worker to exercise the real
pipeline and package data.

For Linux AppImages, `appimagetool` is not bundled. Install it from
[AppImageKit](https://github.com/AppImage/appimagetool) or set `APPIMAGETOOL`:

```bash
APPIMAGETOOL=/path/to/appimagetool make gui-portable
```

On Arch-based systems (including CachyOS), the AUR package is
`appimagetool-bin`.

The CI build uses Ubuntu 22.04 for the Linux artifact so the bundled glibc
baseline is older than current distributions. If FUSE is unavailable on the
target machine, an AppImage still runs with:

```bash
./epub2web-gui-*.AppImage --appimage-extract-and-run
```

### CI and release assets

`.github/workflows/portable.yml` builds Linux x86_64, Windows x64, macOS Intel,
and macOS Apple Silicon in parallel. On a published GitHub release it attaches
the four artifacts and a combined `SHA256SUMS.txt` to that release. The same
workflow can be run manually from **Actions → Portable GUI → Run workflow**.

### Distribution caveats

The portable builds are not code-signed or notarized yet:

- Windows SmartScreen warns on first launch; users choose **More info → Run
  anyway**.
- macOS Gatekeeper blocks unsigned apps; users can right-click **Open**, or run
  `xattr -dr com.apple.quarantine /Applications/epub2web-gui.app`.
- Sign the Windows executable and notarize the macOS `.app`/`.dmg` before a
  wide public release. Those credentials are not stored in the repository.

Portable means "no installation and no Python required". Generated sites still
go to `~/Documents/epub2web/<book>-site`, and logs still go to the platform
application-data directory described above. Removing the app folder does not
remove books or logs.

## Current scope

The GUI supports the same input as the CLI: reflowable EPUB 2/3. Fixed-layout,
image-only, and DRM-protected books are not supported. Remote images are
rejected so the generated site stays self-contained. A failed build leaves an
existing site untouched and produces a support report.
