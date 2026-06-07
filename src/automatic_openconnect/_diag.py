# -*- coding: utf-8 -*-
"""Tiny, dependency-free breadcrumb logger.

Writes a line the instant the exe's Python starts — and at the CLI dispatch
points — to ``%PROGRAMDATA%\\automatic-openconnect\\last-entry.log``. Pure
stdlib (no PyQt6 / no package side-imports) so it runs at the very entry point
BEFORE any heavy import, and so a launch that dies early (e.g. an elevated
Scheduled-Task launch where the PyInstaller bootloader never reaches Python)
leaves a trace — or, by its ABSENCE, proves Python never started.
"""

import os
import sys
import time


def _log_path() -> str:
    d = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
                     "automatic-openconnect")
    return os.path.join(d, "last-entry.log")


def breadcrumb(tag: str = "") -> None:
    """Append a one-line breadcrumb (best-effort; never raises)."""
    try:
        path = _log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        admin = None
        try:
            import ctypes
            admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass
        line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{tag}] "
                f"pid={os.getpid()} admin={admin} "
                f"frozen={getattr(sys, 'frozen', False)} argv={sys.argv}")
        try:
            old = open(path, encoding="utf-8",
                       errors="replace").read().splitlines()[-49:]
        except OSError:
            old = []
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(old + [line]) + "\n")
    except Exception:
        pass


def read_recent(limit: int = 14) -> str:
    """Return the last few breadcrumb lines (for the connect-log diagnostic)."""
    try:
        lines = open(_log_path(), encoding="utf-8",
                     errors="replace").read().splitlines()
        return "\n".join("        " + ln for ln in lines[-limit:])
    except OSError:
        return "        (no last-entry.log — the exe's Python never started)"
