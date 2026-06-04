# src/automatic_openconnect/__main__.py
# -*- coding: utf-8 -*-
"""``python -m automatic_openconnect`` entry point.

Dispatches exactly like the installed ``automatic-vpn`` executable: with no
arguments it launches the GUI; with ``up`` / ``down`` / ``status`` it runs
the headless backend. Handy for running straight from a source checkout
(``uv pip install -e .``) without reinstalling the uv tool on every change.
"""

import sys

from .gui import run

if __name__ == "__main__":
    sys.exit(run())
