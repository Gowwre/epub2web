"""PyInstaller entry point for the epub2web desktop GUI.

Build portable bundles from the repository root:

    pip install -e ".[gui-build]"
    python scripts/build_gui.py

The builder supplies the data files, hidden modules, icon, and platform
packaging flags; this file only routes into :mod:`epub2web.gui`.
"""

from epub2web.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
