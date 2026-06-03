# src/automatic_openconnect/config.py
# -*- coding: utf-8 -*-
"""Per-user configuration storage for the standalone app.

The on-disk schema is the same ``auto_vpn`` block that
``automatic_openconnect._windows`` already consumes. Stored per-user under
``%APPDATA%\\automatic-openconnect\\config.json`` so the app works
regardless of where it is launched and the file stays out of any git
checkout. Credentials are NOT stored here — they live in the keyring
(see ``automatic_openconnect.secrets``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

APP_NAME = "automatic-openconnect"


def config_dir() -> Path:
    """Machine-wide config directory.

    On Windows this is ``%PROGRAMDATA%\\automatic-openconnect`` (i.e.
    ``C:\\ProgramData\\...``), NOT the user's ``%APPDATA%``. The elevated
    Scheduled Task that brings the VPN up runs in a session where the
    user's per-profile AppData (both Roaming and Local) is not visible —
    it appears empty — but ``C:\\ProgramData`` is visible identically to
    both the GUI and the task. Config holds no secrets (those live in the
    OS keyring), so a machine-wide location is appropriate. Falls back to
    ``~/.config`` on platforms without %PROGRAMDATA%/%APPDATA% (Linux/macOS).
    """
    base = (os.environ.get("PROGRAMDATA")
            or os.environ.get("APPDATA")
            or str(Path.home() / ".config"))
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config(path: Optional[Path] = None) -> dict:
    """Return the parsed config, or {} if the file does not exist."""
    p = Path(path) if path is not None else config_path()
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict, path: Optional[Path] = None) -> Path:
    """Write config as UTF-8 JSON, creating parent dirs. Returns the path."""
    p = Path(path) if path is not None else config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return p


def is_configured(data: dict) -> bool:
    """True if the auto_vpn block has the minimum required fields."""
    av = data.get("auto_vpn") or {}
    return bool(av.get("user_email") and av.get("server"))
