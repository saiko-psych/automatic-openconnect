# src/automatic_openconnect/preflight.py
# -*- coding: utf-8 -*-
"""Detect whether everything needed for a VPN connection is present, with a
human-readable fix for anything missing. No Qt import — the GUI renders the
result, the logic stays unit-testable.

Checked prerequisites:
  1. openconnect.exe   — the VPN engine (builds the tunnel / Wintun adapter)
  2. openconnect-sso   — performs the Uni-Graz Keycloak/SAML login
  3. config.toml       — openconnect-sso's auto-fill selectors for Uni-Graz
  4. credentials       — login password + TOTP seed in the OS keyring
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .gui_logic import detect_openconnect, detect_openconnect_sso

CONFIG_TOML = os.path.join(os.path.expanduser("~"), ".config",
                           "openconnect-sso", "config.toml")


@dataclass
class Check:
    name: str
    ok: bool
    fix: str = ""   # instruction shown when not ok


def check_openconnect(path: str = "") -> Check:
    p = (path or "").strip() or detect_openconnect()
    ok = bool(p) and os.path.exists(p)
    return Check(
        "openconnect.exe — VPN-Engine", ok,
        "" if ok else
        "openconnect-gui installieren (enthält openconnect.exe + Wintun-"
        "Treiber): https://github.com/openconnect/openconnect-gui/releases — "
        "danach den Pfad im Setup eintragen.",
    )


def check_openconnect_sso(path: str = "") -> Check:
    p = (path or "").strip() or detect_openconnect_sso()
    ok = bool(p) and os.path.exists(p)
    return Check(
        "openconnect-sso — Login", ok,
        "" if ok else
        'In PowerShell installieren:  uv tool install --with PyQt6 '
        '--with "setuptools<70" openconnect-sso',
    )


def check_config_toml() -> Check:
    ok = os.path.exists(CONFIG_TOML)
    return Check(
        "config.toml — Login-Felder", ok,
        "" if ok else
        f"Fehlt unter {CONFIG_TOML}. Die Uni-Graz-Keycloak-Selektoren-Datei "
        "dort anlegen (Vorlage/Anleitung siehe README, UTF-8 ohne BOM).",
    )


def check_credentials(email: Optional[str]) -> Check:
    if not email:
        return Check(
            "Zugangsdaten im Keyring", False,
            "E-Mail im Setup eintragen, dann Passwort + TOTP-Seed setzen.",
        )
    try:
        from .secrets import get_uni_login_password, get_uni_totp_secret
        ok = bool(get_uni_login_password(email)) and bool(
            get_uni_totp_secret(email))
    except Exception:
        ok = False
    return Check(
        "Zugangsdaten im Keyring", ok,
        "" if ok else
        "Passwort + TOTP-Seed im Setup eintragen (werden sicher im "
        "Windows-Tresor gespeichert).",
    )


def check_all(email: Optional[str] = None,
              openconnect_path: str = "",
              openconnect_sso_path: str = "") -> List[Check]:
    return [
        check_openconnect(openconnect_path),
        check_openconnect_sso(openconnect_sso_path),
        check_config_toml(),
        check_credentials(email),
    ]


def all_ok(checks: List[Check]) -> bool:
    return all(c.ok for c in checks)
