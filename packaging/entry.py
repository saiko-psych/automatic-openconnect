# PyInstaller entry point for the standalone Windows app.
# Dual-mode: `automatic-vpn.exe` launches the GUI; `automatic-vpn.exe up
# --config ...` runs the backend CLI (used by the elevated Scheduled Task).
import sys

# Breadcrumb the INSTANT Python starts — before importing gui/PyQt6 — so a
# launch that dies early (e.g. an elevated Scheduled-Task launch) leaves a
# trace, or by its absence proves Python never started.
try:
    from automatic_openconnect._diag import breadcrumb
    breadcrumb("entry")
except Exception:
    pass

from automatic_openconnect.gui import run

if __name__ == "__main__":
    sys.exit(run())
