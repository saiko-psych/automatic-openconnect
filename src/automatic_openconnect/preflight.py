# src/automatic_openconnect/preflight.py
# -*- coding: utf-8 -*-
"""Detect whether everything needed for a VPN connection is present, with a
human-readable fix for anything missing. No Qt import — the GUI renders the
result, the logic stays unit-testable.

Checked prerequisites:
  1. openconnect.exe   — the VPN engine (builds the tunnel / Wintun adapter)
  2. Wintun driver     — wintun.dll next to openconnect (ships with
                         OpenConnect-GUI); a warning only, never blocking
  3. openconnect-sso   — performs the Keycloak/SAML login
  4. config.toml       — openconnect-sso's auto-fill selectors (the bundled
                         template defaults to Uni Graz; see CONFIG_TOML_TEMPLATE)
  5. credentials       — login password + TOTP seed in the OS keyring
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from .gui_logic import detect_openconnect, detect_openconnect_sso

CONFIG_TOML = os.path.join(os.path.expanduser("~"), ".config",
                           "openconnect-sso", "config.toml")


# openconnect-gui releases page (provides openconnect.exe + Wintun driver).
OPENCONNECT_GUI_RELEASES = \
    "https://github.com/openconnect/openconnect-gui/releases"


@dataclass
class Check:
    name: str        # i18n key, e.g. "check.openconnect"
    ok: bool
    fix: str = ""    # i18n key for the instruction shown when not ok
    action: str = ""  # machine key the GUI maps to a fix button:
    #                   "open_download" | "install_sso" | "create_config"
    #                   | "open_setup"  (empty = no automated action)
    warn_only: bool = False  # advisory only — does NOT block (see all_ok);
    #                          used for heuristic checks like Wintun.


def check_openconnect(path: str = "") -> Check:
    # Use the configured path if it resolves; otherwise re-detect LIVE so a
    # tool installed after setup (or under a stale/empty path) is still found.
    p = (path or "").strip()
    ok = bool(p) and os.path.exists(p)
    if not ok:
        d = detect_openconnect()
        ok = bool(d) and os.path.exists(d)
    return Check("check.openconnect", ok,
                 "" if ok else "fix.openconnect",
                 "" if ok else "open_download")


def _wintun_present(openconnect_path: str = "") -> bool:
    """Heuristic: is wintun.dll where openconnect can load it? OpenConnect-GUI
    ships it next to openconnect.exe; it may also live in System32/SysWOW64."""
    p = (openconnect_path or "").strip()
    oc_dir = os.path.dirname(p) if (p and os.path.exists(p)) else ""
    if not oc_dir:
        d = detect_openconnect()
        oc_dir = os.path.dirname(d) if d else ""
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        os.path.join(oc_dir, "wintun.dll") if oc_dir else "",
        os.path.join(sysroot, "System32", "wintun.dll"),
        os.path.join(sysroot, "SysWOW64", "wintun.dll"),
    ]
    return any(c and os.path.exists(c) for c in candidates)


def check_wintun(openconnect_path: str = "") -> Check:
    """Warn (never block) if the Wintun driver is missing. Only meaningful
    once openconnect itself is found — otherwise the openconnect check
    already tells the user to install OpenConnect-GUI (which bundles Wintun)."""
    oc = (openconnect_path or "").strip()
    oc_found = (bool(oc) and os.path.exists(oc)) or bool(detect_openconnect())
    if not oc_found:
        return Check("check.wintun", True, warn_only=True)
    ok = _wintun_present(openconnect_path)
    return Check("check.wintun", ok,
                 "" if ok else "fix.wintun",
                 "" if ok else "open_download",
                 warn_only=True)


def check_openconnect_sso(path: str = "") -> Check:
    p = (path or "").strip()
    ok = bool(p) and os.path.exists(p)
    if not ok:
        d = detect_openconnect_sso()
        ok = bool(d) and os.path.exists(d)
    return Check("check.sso", ok,
                 "" if ok else "fix.sso",
                 "" if ok else "install_sso")


def check_config_toml() -> Check:
    ok = os.path.exists(CONFIG_TOML)
    return Check("check.config", ok,
                 "" if ok else "fix.config",
                 "" if ok else "create_config")


def check_credentials(email: Optional[str]) -> Check:
    if not email:
        return Check("check.credentials", False,
                     "fix.credentials_noemail", "open_setup")
    try:
        from .secrets import get_uni_login_password, get_uni_totp_secret
        ok = bool(get_uni_login_password(email)) and bool(
            get_uni_totp_secret(email))
    except Exception:
        ok = False
    return Check("check.credentials", ok,
                 "" if ok else "fix.credentials",
                 "" if ok else "open_setup")


# --- automated fixes ----------------------------------------------------

CONFIG_TOML_TEMPLATE = '''\
on_disconnect = ""

[default_profile]
address = "univpn.uni-graz.at"
user_group = ""
name = ""

[auto_fill_rules]
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#username"
fill = "username"

[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#password"
fill = "password"

[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#kc-login"
action = "click"

[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input[name=otp]"
fill = "totp"

[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#kc-login"
action = "click"

[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#kc-accept"
action = "click"

[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "span#input-error"
action = "stop"
'''


def create_config_toml() -> str:
    """Write the Uni-Graz openconnect-sso config.toml template (UTF-8, no
    BOM). Returns the path. Raises OSError on failure."""
    path = CONFIG_TOML
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(CONFIG_TOML_TEMPLATE)
    return path


def install_sso_command() -> List[str]:
    """argv to install openconnect-sso as a uv tool (network, no admin).
    Returns [] if uv cannot be located — the GUI then offers to install uv."""
    from .gui_logic import resolve_uv
    uv = resolve_uv()
    if not uv:
        return []
    return uv + ["tool", "install", "--with", "PyQt6",
                 "--with", "setuptools<70", "openconnect-sso"]


def check_all(email: Optional[str] = None,
              openconnect_path: str = "",
              openconnect_sso_path: str = "") -> List[Check]:
    return [
        check_openconnect(openconnect_path),
        check_wintun(openconnect_path),
        check_openconnect_sso(openconnect_sso_path),
        check_config_toml(),
        check_credentials(email),
    ]


def all_ok(checks: List[Check]) -> bool:
    """True if every *blocking* check passed. Advisory (warn_only) checks
    never block a connection attempt."""
    return all(c.ok for c in checks if not c.warn_only)
