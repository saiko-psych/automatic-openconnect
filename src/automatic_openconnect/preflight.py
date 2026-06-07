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

import ntpath
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

from .gui_logic import (detect_openconnect, detect_openconnect_sso,
                        normalize_openconnect_path)

CONFIG_TOML = os.path.join(os.path.expanduser("~"), ".config",
                           "openconnect-sso", "config.toml")


# Official OpenConnect-GUI download page. NOT the GitHub releases page —
# that one has no assets, which is why testers ended up grabbing loose
# openconnect.exe files that don't work. The installer here bundles
# openconnect.exe + its DLLs + the vpnc routing script + the Wintun driver.
OPENCONNECT_GUI_RELEASES = "https://gui.openconnect-vpn.net/download/"


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
    # normalize_openconnect_path heals a folder / openconnect-gui.exe / stale
    # path and auto-detects, so the check reflects the real openconnect the
    # backend will run — and a directory no longer shows up as a false "OK".
    resolved = normalize_openconnect_path(path)
    ok = bool(resolved) and os.path.isfile(resolved)
    if ok:
        return Check("check.openconnect", True)
    if sys.platform == "win32":
        # Windows: the OpenConnect-GUI installer provides openconnect.exe.
        return Check("check.openconnect", False, "fix.openconnect",
                     "open_download")
    # Linux / macOS: installed via the package manager (no download button).
    return Check("check.openconnect", False, "fix.openconnect_unix", "")


def _wintun_present(openconnect_path: str = "") -> bool:
    """Heuristic: is wintun.dll where openconnect can load it? OpenConnect-GUI
    ships it next to openconnect.exe; it may also live in System32/SysWOW64."""
    p = (openconnect_path or "").strip()
    oc_dir = ntpath.dirname(p) if (p and os.path.exists(p)) else ""
    if not oc_dir:
        d = detect_openconnect()
        oc_dir = ntpath.dirname(d) if d else ""
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        ntpath.join(oc_dir, "wintun.dll") if oc_dir else "",
        ntpath.join(sysroot, "System32", "wintun.dll"),
        ntpath.join(sysroot, "SysWOW64", "wintun.dll"),
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


def _vpnc_script_present(openconnect_path: str = "") -> bool:
    """Is openconnect's routing script next to it? OpenConnect-GUI ships
    vpnc-script-win.js; a loose openconnect.exe won't have it."""
    p = (openconnect_path or "").strip()
    oc_dir = ntpath.dirname(p) if (p and os.path.exists(p)) else ""
    if not oc_dir:
        d = detect_openconnect()
        oc_dir = ntpath.dirname(d) if d else ""
    if not oc_dir:
        return False
    return any(os.path.exists(ntpath.join(oc_dir, n))
               for n in ("vpnc-script-win.js", "vpnc-script.js"))


def check_vpnc_script(openconnect_path: str = "") -> Check:
    """Warn (never block) if openconnect's routing script isn't beside it —
    the tell-tale of a loose openconnect.exe instead of a full OpenConnect-GUI
    install. Without it the tunnel fails with 'canonicalize script path'."""
    oc = (openconnect_path or "").strip()
    oc_found = (bool(oc) and os.path.exists(oc)) or bool(detect_openconnect())
    if not oc_found:
        return Check("check.vpnc", True, warn_only=True)
    ok = _vpnc_script_present(openconnect_path)
    return Check("check.vpnc", ok,
                 "" if ok else "fix.vpnc",
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

_CONFIG_TOML_HEAD = '''\
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
'''

# OTP step (the page with the credential tiles). Comes AFTER the optional
# tile-selection rule injected by _slot_rule().
_CONFIG_TOML_OTP = '''
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


def _slot_rule(token_slot: int) -> str:
    """Rule to click the chosen 2FA token tile before typing the code.

    Keycloak shows one tile per registered OTP credential (radio buttons with
    per-account GUID ids, so we select by POSITION) and validates the code
    against the *selected* one. Only emitted when a slot is configured —
    single-token users have no selector page, so we must not wait on it.
    """
    n = int(token_slot or 0)
    if n < 1:
        return ""
    return (
        '\n[[auto_fill_rules."https://login.uni-graz.at/*"]]\n'
        f'selector = ".otp-device--selector label:nth-of-type({n})"\n'
        'action = "click"\n'
    )


def build_config_toml(token_slot: int = 0) -> str:
    """The Uni-Graz openconnect-sso config.toml, optionally selecting the
    Nth 2FA token tile (token_slot >= 1) before entering the code."""
    return _CONFIG_TOML_HEAD + _slot_rule(token_slot) + _CONFIG_TOML_OTP


# Back-compat alias (no tile selection).
CONFIG_TOML_TEMPLATE = build_config_toml(0)


def create_config_toml(token_slot: int = 0) -> str:
    """Write the openconnect-sso config.toml (UTF-8, no BOM). With
    token_slot >= 1, the Nth credential tile is auto-selected. Returns the
    path; raises OSError on failure."""
    path = CONFIG_TOML
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_config_toml(token_slot))
    return path


def install_sso_command() -> List[str]:
    """argv to install openconnect-sso as a uv tool (network, no admin).
    Returns [] if uv cannot be located — the GUI then offers to install uv."""
    from .gui_logic import resolve_uv
    uv = resolve_uv()
    if not uv:
        return []
    # Pin a known-good managed Python: openconnect-sso 0.8.1 + its deps don't
    # have wheels for bleeding-edge interpreters (e.g. 3.14), which makes the
    # install fail. uv downloads 3.12 if needed.
    return uv + ["tool", "install", "--python", "3.12", "--with", "PyQt6",
                 "--with", "setuptools<70", "openconnect-sso"]


def check_all(email: Optional[str] = None,
              openconnect_path: str = "",
              openconnect_sso_path: str = "") -> List[Check]:
    checks = [check_openconnect(openconnect_path)]
    # Wintun + the vpnc-script-win.js routing script are Windows-only concepts
    # (a loose openconnect.exe ships without them). On Linux/macOS openconnect
    # uses the kernel tun/utun device and its built-in vpnc-script, so these
    # checks don't apply.
    if sys.platform == "win32":
        checks.append(check_wintun(openconnect_path))
        checks.append(check_vpnc_script(openconnect_path))
    checks += [
        check_openconnect_sso(openconnect_sso_path),
        check_config_toml(),
        check_credentials(email),
    ]
    return checks


def all_ok(checks: List[Check]) -> bool:
    """True if every *blocking* check passed. Advisory (warn_only) checks
    never block a connection attempt."""
    return all(c.ok for c in checks if not c.warn_only)
