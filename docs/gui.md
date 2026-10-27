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
- `scripts/gui_entry.py` — PyInstaller entry point.

The view sends user actions to `BuildController`; the controller spawns a
worker and emits `BuildEvent` objects. The Tk app puts those events on a queue
and applies them on the Tk main thread. Replacing Tkinter with Qt or a local web
view should not require changes to the controller or worker.

## Building a standalone app

Install PyInstaller and build from the repository root:

```bash
pip install -e ".[gui-build]"
pyinstaller --noconfirm --clean --windowed --name epub2web-gui \
  --paths . --collect-data epub2web --collect-submodules epub2web \
  scripts/gui_entry.py
```

`--collect-data` is required for the templates, theme CSS/JavaScript, and
self-hosted fonts. `--collect-submodules` keeps the dynamically imported worker
and Tk modules available.

The result is `dist/epub2web-gui/` (or `.app` on macOS). Use a one-folder build;
a one-file build works too, but the worker re-extracts the bundle each time it
starts.

When the app is frozen, the controller runs the worker by launching the same
executable with a hidden `--worker` flag. That is why `sys.executable -m
epub2web` is not used in a packaged build.

Release builds still need the normal platform work:

- test on Windows, macOS (Intel and Apple Silicon), and Linux;
- sign the Windows executable and notarize the macOS app;
- provide the platform Tk/runtime libraries through PyInstaller;
- run the same smoke test on each platform: choose an EPUB, convert it, open
  the preview, stop the server, close the window.

## Current scope

The GUI supports the same input as the CLI: reflowable EPUB 2/3. Fixed-layout,
image-only, and DRM-protected books are not supported. Remote images are
rejected so the generated site stays self-contained. A failed build leaves an
existing site untouched and produces a support report.
