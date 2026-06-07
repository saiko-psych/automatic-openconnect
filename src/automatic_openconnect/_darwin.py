# -*- coding: utf-8 -*-
"""
automatic_openconnect._darwin — macOS headless VPN backend.

Mirrors :mod:`automatic_openconnect._linux`: two-stage bring-up via
openconnect-sso (SAML/2FA auth in a Qt-WebEngine browser, credentials from
the Keychain via ``keyring``) → classic ``openconnect`` builds the tunnel.

macOS differences from Linux:

* **No xvfb** — a macOS GUI session already has a display, so the
  openconnect-sso browser shows directly.
* **No** ``/proc`` — process liveness is checked with ``os.kill(pid, 0)``.
* The tunnel device is a ``utunN`` (assigned dynamically), not ``tun0``.
* ``openconnect`` is typically Homebrew's ``/opt/homebrew/bin/openconnect``
  (Apple Silicon) or ``/usr/local/bin/openconnect`` (Intel) — resolved via
  PATH / the configured override.

Threat model: ``openconnect`` needs root for the utun device. Headless use
relies on a sudoers NOPASSWD rule (same as Linux); the GUI elevates the whole
``up`` command instead (osascript "with administrator privileges"), so inside
that elevated process ``sudo -n`` is already satisfied.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Tuple

from .core import VPNError  # re-export


# --- platform + tool guards ---------------------------------------------

def _check_darwin(operation: str) -> None:
    if sys.platform != "darwin":
        raise VPNError(
            f"auto_vpn.{operation} is only supported on macOS "
            f"(detected: {sys.platform!r})."
        )


def _check_keyring_credentials(cfg: dict) -> None:
    from .secrets import get_uni_login_password, get_uni_totp_secret
    email = cfg["user_email"]
    if not get_uni_login_password(email):
        raise VPNError(
            f"No login password in keyring for {email!r} (openconnect-sso "
            "namespace). Populate it first:\n"
            f"  python -m automatic_openconnect.secrets set --email {email} --vpn"
        )
    if not get_uni_totp_secret(email):
        raise VPNError(
            f"No TOTP base32 seed in keyring for {email!r}. The same command "
            "sets both:\n"
            f"  python -m automatic_openconnect.secrets set --email {email} --vpn"
        )


def _resolve_tool(name: str, override_path: str = "") -> str:
    """Return the path to a CLI tool, or raise VPNError with an install hint."""
    if override_path and shutil.which(override_path):
        return override_path
    resolved = shutil.which(name)
    if not resolved:
        raise VPNError(
            f"required tool {name!r} not found in PATH. Install it "
            "(e.g. `brew install openconnect`, `uv tool install openconnect-sso`)."
        )
    return resolved


def is_vpn_up(server_hint: str = "univpn") -> bool:
    """Cheap check: is an openconnect process talking to the server?

    Uses pgrep (present on macOS). Returns False on other platforms.
    """
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"openconnect.*{server_hint}"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# --- the two-stage VPN bring-up -----------------------------------------

def _authenticate(cfg: dict) -> Tuple[str, str, str]:
    """Run openconnect-sso --authenticate and parse HOST/COOKIE/FINGERPRINT."""
    sso_path = _resolve_tool(
        "openconnect-sso", cfg.get("openconnect_sso_path", "")
    )
    cmd = [
        sso_path,
        "-u", cfg["user_email"],
        "--browser-display-mode", "shown",
        "-l", "INFO",
        "--authenticate",
    ]
    print("[auto_vpn] Authenticating via openconnect-sso ...", file=sys.stderr)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise VPNError("openconnect-sso authentication timed out after 180s")

    if result.returncode != 0:
        raise VPNError(
            f"openconnect-sso failed (exit {result.returncode}). "
            f"stderr tail:\n{(result.stderr or '')[-500:].strip()}"
        )

    host = cookie = fingerprint = None
    for line in (result.stdout or "").splitlines():
        if line.startswith("HOST="):
            host = line.split("=", 1)[1].strip()
        elif line.startswith("COOKIE="):
            cookie = line.split("=", 1)[1].strip()
        elif line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1].strip()

    if not all([host, cookie, fingerprint]):
        raise VPNError(
            "openconnect-sso did not return HOST/COOKIE/FINGERPRINT. "
            f"First 200 chars of stdout: {(result.stdout or '')[:200]!r}"
        )
    return host, cookie, fingerprint


def _pid_alive(pid: int) -> bool:
    """True if a process with this PID exists (cross-platform, no /proc)."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _start_tunnel(host: str, cookie: str, fingerprint: str, cfg: dict) -> None:
    """Spawn openconnect in the background with the given SAML cookie.

    Same detach strategy as Linux (DEVNULL pipes + new session so
    ``--background`` daemonizes cleanly), but liveness is verified via
    ``os.kill(pid, 0)`` since macOS has no ``/proc``.
    """
    oc_path = _resolve_tool("openconnect", cfg.get("openconnect_path", ""))
    pid_file = cfg.get("pid_file", "/tmp/oc-automatic.pid")

    cmd = [
        "sudo", "-n", oc_path,
        "--servercert", fingerprint,
        "--cookie", cookie,
        "--background",
        "--pid-file", pid_file,
        "--no-dtls",
        host,
    ]
    print("[auto_vpn] Starting tunnel ...", file=sys.stderr)
    try:
        subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            start_new_session=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise VPNError(
            "openconnect spawn timed out after 15s. Most likely the sudoers "
            "NOPASSWD rule is missing — sudo is prompting for a password and "
            "blocking."
        )

    # openconnect writes its daemon PID once it has forked. Verify it is a
    # live process (utun creation lags the spawn by a beat).
    for _ in range(12):
        try:
            pid = int(open(pid_file).read().strip())
            if _pid_alive(pid):
                print("[auto_vpn] openconnect daemon is up", file=sys.stderr)
                return
        except (FileNotFoundError, ValueError, OSError):
            pass
        time.sleep(1)
    raise VPNError(
        f"openconnect did not register a running PID at {pid_file} within 12s. "
        "Run the same openconnect command manually to diagnose."
    )


def _stop_tunnel(server_hint: str = "univpn") -> None:
    """Kill openconnect processes for the configured VPN server (macOS)."""
    if sys.platform != "darwin":
        return
    pattern = f"openconnect.*{server_hint}"
    pids = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    for pid in pids:
        try:
            subprocess.run(
                ["sudo", "-n", "/bin/kill", pid],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=5,
            )
        except subprocess.TimeoutExpired:
            print(f"[auto_vpn] WARN: sudo kill {pid} timed out", file=sys.stderr)

    time.sleep(1)
    try:
        still = subprocess.run(
            ["pgrep", "-f", pattern],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5,
        )
        if still.returncode == 0:
            subprocess.run(
                ["sudo", "-n", "/usr/bin/pkill", "openconnect"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, timeout=5,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


# --- public context manager ---------------------------------------------

@contextmanager
def auto_vpn_session(config_data: dict):
    """Context manager that brings the VPN up around the wrapped block.

    No-op when ``config_data['auto_vpn'].enabled`` is not True. Cleanup is
    guaranteed on normal exit and on exception — but only if WE brought the
    tunnel up (an already-running tunnel is left alone).
    """
    cfg = (config_data.get("auto_vpn") or {})
    if not cfg.get("enabled"):
        yield None
        return

    _check_darwin("auto_vpn_session")

    if not cfg.get("user_email"):
        raise VPNError(
            "auto_vpn.user_email is required when auto_vpn.enabled is true"
        )

    server = cfg.get("server", "univpn.uni-graz.at")
    server_hint = server.split(".")[0]
    was_already_up = is_vpn_up(server_hint)

    if not was_already_up:
        _check_keyring_credentials(cfg)
        try:
            host, cookie, fingerprint = _authenticate(cfg)
            _start_tunnel(host, cookie, fingerprint, cfg)
        except BaseException:
            print("[auto_vpn] Setup failed - cleaning up partial tunnel",
                  file=sys.stderr)
            _stop_tunnel(server_hint)
            raise
        del cookie

    try:
        yield True
    finally:
        if cfg.get("down_on_exit", True) and not was_already_up:
            print("[auto_vpn] Closing tunnel", file=sys.stderr)
            _stop_tunnel(server_hint)
