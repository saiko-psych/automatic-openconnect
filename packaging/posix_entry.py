# packaging/posix_entry.py
# PyInstaller entry point for the Linux/macOS binary: launch the lean tray.
# (Windows is built from automatic-vpn.spec → the full GUI; this is posix-only.)
import sys

from automatic_openconnect._posix_tray import run

if __name__ == "__main__":
    sys.exit(run())
