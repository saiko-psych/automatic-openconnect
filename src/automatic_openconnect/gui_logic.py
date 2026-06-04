# src/automatic_openconnect/gui_logic.py
# -*- coding: utf-8 -*-
"""Pure logic for the standalone app — NO PyQt6 import (CI-testable).

Holds the decisions the GUI makes so they can be unit-tested without a Qt
event loop: which view to show, whether the setup form is valid, how to
build the config block, and where the binaries live by default.
"""

from __future__ import annotations

import os
import shutil
from typing import List

from .config import is_configured

_STD_OPENCONNECT = r"C:\Program Files\OpenConnect-GUI\openconnect.exe"


def connect_step_label(log_text: str) -> str:
    """Map the latest known marker in the connect log to a coarse step KEY
    (translated by the GUI). Order matters: check the latest stages first.
    """
    t = log_text
    if "Traceback (most recent call last)" in t or "FAIL:" in t:
        return "step.failed"
    if "route configuration done" in t or "Tunnel is up" in t:
        return "step.almost"
    if "Starting openconnect.exe" in t or "[openconnect]" in t:
        return "step.tunnel"
    if "Authenticating via openconnect-sso" in t:
        return "step.signing_in"
    if "bringing tunnel up" in t or "Stopping" in t:
        return "step.preparing"
    return "step.connecting"


def choose_view(config: dict, registered: bool) -> str:
    """Return 'setup' until config is complete AND tasks are registered."""
    if not is_configured(config) or not registered:
        return "setup"
    return "control"


def detect_openconnect() -> str:
    """Best guess for openconnect.exe: standard install path, else PATH."""
    if os.path.exists(_STD_OPENCONNECT):
        return _STD_OPENCONNECT
    return shutil.which("openconnect") or ""


def detect_openconnect_sso() -> str:
    """Best guess for openconnect-sso(.exe): PATH lookup."""
    return shutil.which("openconnect-sso") or ""


def validate_setup_form(fields: dict) -> List[str]:
    """Return a list of error KEYS (translated by the GUI); empty = valid."""
    errors: List[str] = []
    if not (fields.get("email") or "").strip():
        errors.append("err.email_empty")
    if not (fields.get("server") or "").strip():
        errors.append("err.server_empty")
    oc = (fields.get("openconnect_path") or "").strip()
    if not oc or not os.path.exists(oc):
        errors.append("err.openconnect_missing")
    sso = (fields.get("openconnect_sso_path") or "").strip()
    if not sso or not os.path.exists(sso):
        errors.append("err.sso_missing")
    return errors


def parse_services(text: str) -> list:
    """Parse a comma/whitespace-separated list of service names."""
    return [s.strip() for s in (text or "").replace(",", " ").split()
            if s.strip()]


def build_auto_vpn_config(*, email: str, server: str, openconnect_path: str,
                          openconnect_sso_path: str,
                          stop_conflicting: bool = True,
                          conflicting_services: list = None) -> dict:
    """Build the config.json dict the _windows backend consumes."""
    from ._windows import DEFAULT_CONFLICTING_SERVICES
    services = (conflicting_services if conflicting_services is not None
                else list(DEFAULT_CONFLICTING_SERVICES))
    return {
        "auto_vpn": {
            "enabled": True,
            "user_email": email.strip(),
            "server": server.strip(),
            "openconnect_path": openconnect_path.strip(),
            "openconnect_sso_path": openconnect_sso_path.strip(),
            "stop_conflicting_services": bool(stop_conflicting),
            "conflicting_services": services,
            "down_on_exit": True,
        }
    }
