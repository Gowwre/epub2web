"""PyInstaller entry point for the epub2web desktop GUI.

Build from the repository root after installing the package:

    pip install -e ".[gui-build]"
    pyinstaller --noconfirm --clean --windowed --name epub2web-gui \
      --paths . --collect-data epub2web --collect-submodules epub2web \
      scripts/gui_entry.py
"""

from epub2web.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
