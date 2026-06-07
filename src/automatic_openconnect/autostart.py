# -*- coding: utf-8 -*-
"""
automatic_openconnect.autostart
===============================

Cross-platform "start at login" support, so the app comes up silently in the
tray at login and keeps the global TOTP hotkey available.

Per platform (all *non-elevated*, current-user only):

* **Windows** — the per-user Run key
  ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``.
* **Linux** — an XDG autostart desktop entry
  ``~/.config/autostart/automatic-openconnect.desktop``.
* **macOS** — a LaunchAgent plist in ``~/Library/LaunchAgents``.

Platform-specific modules (``winreg``) are imported lazily so this module
imports everywhere (incl. CI), and the logic is unit-tested on the Linux CI.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import sys
from typing import List, Optional

log = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "automatic-openconnect"
_LAUNCH_AGENT_ID = "com.github.saiko-psych.automatic-openconnect"
_APP_NAME = "automatic VPN"


def launch_argv() -> List[str]:
    """argv to relaunch the GUI at login (list form, for .desktop / plist).

    - Frozen one-file exe → the exe itself.
    - uv tool / pip install → the ``automatic-vpn`` launcher on PATH.
    - Dev / fallback → ``<python> -m automatic_openconnect`` (windowless
      ``pythonw.exe`` on Windows when present).
    """
    if getattr(sys, "frozen", False):
        return [sys.executable]
    launcher = shutil.which("automatic-vpn")
    if launcher:
        return [launcher]
    exe = sys.executable
    if sys.platform == "win32":
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.exists(pyw):
            exe = pyw
    return [exe, "-m", "automatic_openconnect"]


def launch_command() -> str:
    """The relaunch command as a single string (Windows registry value)."""
    argv = launch_argv()
    if len(argv) == 1:
        return f'"{argv[0]}"'
    # quote the executable, leave the module args bare (matches prior format)
    return '"%s" %s' % (argv[0], " ".join(argv[1:]))


# --- XDG (Linux) ---------------------------------------------------------

def _desktop_file() -> str:
    base = (os.environ.get("XDG_CONFIG_HOME")
            or os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(base, "autostart", "automatic-openconnect.desktop")


def _desktop_entry() -> str:
    exec_line = shlex.join(launch_argv())
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={_APP_NAME}\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


# --- LaunchAgent (macOS) -------------------------------------------------

def _launch_agent_plist_path() -> str:
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents",
                        f"{_LAUNCH_AGENT_ID}.plist")


def _launch_agent_plist() -> str:
    args = "".join(f"        <string>{a}</string>\n" for a in launch_argv())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        '<dict>\n'
        '    <key>Label</key>\n'
        f'    <string>{_LAUNCH_AGENT_ID}</string>\n'
        '    <key>ProgramArguments</key>\n'
        '    <array>\n'
        f'{args}'
        '    </array>\n'
        '    <key>RunAtLoad</key>\n'
        '    <true/>\n'
        '</dict>\n'
        '</plist>\n'
    )


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
        log.info("autostart disabled: %s", path)
    except FileNotFoundError:
        pass
    except OSError as exc:  # pragma: no cover - platform dependent
        log.warning("autostart disable failed: %s", exc)


# --- public, platform-dispatching API ------------------------------------

def is_enabled() -> bool:
    """True if our autostart entry exists (never raises)."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, _VALUE_NAME)
            return True
        except OSError:
            return False
    if sys.platform == "darwin":
        return os.path.exists(_launch_agent_plist_path())
    return os.path.exists(_desktop_file())


def enable(command: Optional[str] = None) -> None:
    """Register the app to start at login (overwrites any existing entry)."""
    if sys.platform == "win32":
        import winreg
        cmd = command or launch_command()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, cmd)
        log.info("autostart enabled: %s", cmd)
        return
    if sys.platform == "darwin":
        _write(_launch_agent_plist_path(), _launch_agent_plist())
        log.info("autostart enabled (LaunchAgent)")
        return
    _write(_desktop_file(), _desktop_entry())
    log.info("autostart enabled (XDG desktop entry)")


def disable() -> None:
    """Remove the autostart entry if present (never raises)."""
    if sys.platform == "win32":
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
        return
    if sys.platform == "darwin":
        _safe_remove(_launch_agent_plist_path())
        return
    _safe_remove(_desktop_file())


def set_enabled(enabled: bool) -> None:
    """Convenience: enable or disable to match a checkbox state."""
    if enabled:
        enable()
    else:
        disable()
