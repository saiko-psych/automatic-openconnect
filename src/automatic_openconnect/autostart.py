# -*- coding: utf-8 -*-
"""
automatic_openconnect.autostart
===============================

Windows "start at login" support via the per-user Run registry key,
``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``.

This is the standard *non-elevated* autostart location: nothing here needs
admin rights and it only affects the current user. We register the windowed
launcher so the app comes up silently in the tray at login — which keeps the
global TOTP hotkey available without the user opening anything.

``winreg`` is imported lazily inside each function so the module still
imports on Linux/macOS (and under CI), where only :func:`launch_command` is
meaningful and unit-tested.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from typing import Optional

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "automatic-openconnect"


def launch_command() -> str:
    """The best command to relaunch the GUI at login, quoted for the registry.

    - Frozen one-file exe → the exe itself.
    - uv tool / pip install → the windowed ``automatic-vpn`` launcher on PATH.
    - Dev / fallback → ``pythonw.exe -m automatic_openconnect`` (windowless).
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    launcher = shutil.which("automatic-vpn")
    if launcher:
        return f'"{launcher}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" -m automatic_openconnect'


def is_enabled() -> bool:
    """True if our autostart entry exists (never raises)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable(command: Optional[str] = None) -> None:
    """Register the app to start at login (overwrites any existing entry)."""
    import winreg
    cmd = command or launch_command()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, cmd)
    log.info("autostart enabled: %s", cmd)


def disable() -> None:
    """Remove the autostart entry if present (never raises)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        log.info("autostart disabled")
    except FileNotFoundError:
        pass
    except OSError as exc:  # pragma: no cover - platform dependent
        log.warning("autostart disable failed: %s", exc)


def set_enabled(enabled: bool) -> None:
    """Convenience: enable or disable to match a checkbox state."""
    if enabled:
        enable()
    else:
        disable()
