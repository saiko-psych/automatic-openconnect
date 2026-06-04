# PyInstaller entry point for the standalone Windows app.
# Dual-mode: `automatic-vpn.exe` launches the GUI; `automatic-vpn.exe up
# --config ...` runs the backend CLI (used by the elevated Scheduled Task).
import sys

from automatic_openconnect.gui import run

if __name__ == "__main__":
    sys.exit(run())
