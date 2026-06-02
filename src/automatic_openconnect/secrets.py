# -*- coding: utf-8 -*-
"""
automatic_openconnect.secrets
=============================

Keyring access for the VPN credentials, extracted from Termino's
``utils.secrets``. Only the ``openconnect-sso`` namespace lives here -
the Termino-specific secrets (Termino password, uniCLOUD app password,
mail passwords) stay in the Termino project.

Backend selection
-----------------
Driven by ``PYTHON_KEYRING_BACKEND`` per the python-keyring convention.
This module never picks the backend itself - that would couple the code
to a deployment.

- Desktop (KDE / GNOME / macOS / Windows): leave it unset -> the OS
  default keyring is used (Secret Service / KDE Wallet / Keychain /
  Credential Manager).
- Headless server / LXC / container with cron::

      PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring

  Make the store owner-only readable BEFORE the first write::

      chmod 700 ~/.local/share/python_keyring/
      chmod 600 ~/.local/share/python_keyring/keyring_pass.cfg

  pip dependency for that backend: ``keyrings.alt``.

Key naming convention
---------------------
The service name is ``openconnect-sso`` - the *same* namespace and key
layout that openconnect-sso itself uses, so a single keyring entry serves
both the VPN login and (in Termino) the EWS Basic Auth. The login
password is keyed by the email address; the TOTP base32 seed is the same
email prefixed with ``totp/``.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Optional

import keyring
import keyring.errors


# --- service name -------------------------------------------------------

SERVICE_VPN = "openconnect-sso"  # matches openconnect-sso's own convention


# --- known keys (documented so we never typo them) ----------------------

VPN_KEY_PATTERN: dict[str, str] = {
    "<email>": "The user's normal login password. Used by openconnect-sso "
               "(VPN login) and, in Termino, by exchangelib (EWS Basic Auth).",
    "totp/<email>": "TOTP shared secret in base32 (the seed, not the 6-digit "
                    "code). openconnect-sso generates the rotating code from it.",
}


# --- low-level API ------------------------------------------------------

def get_secret(key: str, service: str = SERVICE_VPN) -> Optional[str]:
    """Return the secret stored under ``service``/``key`` or None if missing."""
    return keyring.get_password(service, key)


def set_secret(key: str, value: str, service: str = SERVICE_VPN) -> None:
    """Store a secret. Overwrites any existing value silently."""
    keyring.set_password(service, key, value)


def delete_secret(key: str, service: str = SERVICE_VPN) -> None:
    """Remove a secret. Raises keyring.errors.PasswordDeleteError if absent."""
    keyring.delete_password(service, key)


# --- VPN-credential helpers (convenience wrappers) ----------------------

def get_uni_login_password(email: str) -> Optional[str]:
    """Fetch the login password from the openconnect-sso namespace."""
    return get_secret(email, service=SERVICE_VPN)


def get_uni_totp_secret(email: str) -> Optional[str]:
    """Fetch the TOTP base32 seed from the openconnect-sso namespace."""
    return get_secret(f"totp/{email}", service=SERVICE_VPN)


def set_uni_login_password(email: str, password: str) -> None:
    set_secret(email, password, service=SERVICE_VPN)


def set_uni_totp_secret(email: str, base32_seed: str) -> None:
    set_secret(f"totp/{email}", base32_seed, service=SERVICE_VPN)


# --- diagnostics --------------------------------------------------------

def backend_info() -> dict[str, str]:
    """Return information about the active keyring backend for debugging."""
    kr = keyring.get_keyring()
    return {
        "name": kr.name,
        "class": f"{type(kr).__module__}.{type(kr).__name__}",
    }


# --- CLI ----------------------------------------------------------------

def _cli_set(args: argparse.Namespace) -> int:
    """Interactively set the VPN login password and TOTP seed."""
    if not args.email:
        print("ERROR: --email is required.", file=sys.stderr)
        return 2

    print(f"Setting VPN credentials for {args.email}:")
    print("(Type the value at each prompt, or press Enter to keep the current one.)")

    current_pw = "already set" if get_uni_login_password(args.email) else "not set"
    print(f"\n  Login password  [{current_pw}]")
    pw = getpass.getpass("    new value (Enter to keep): ")
    if pw:
        set_uni_login_password(args.email, pw)
        print("    OK login password stored.")
    else:
        print("    (kept)")

    current_totp = "already set" if get_uni_totp_secret(args.email) else "not set"
    print(f"\n  TOTP secret base32  [{current_totp}]")
    totp = getpass.getpass("    new value (Enter to keep): ")
    if totp:
        set_uni_totp_secret(args.email, totp.replace(" ", ""))
        print("    OK TOTP secret stored.")
    else:
        print("    (kept)")

    return 0


def _cli_get(args: argparse.Namespace) -> int:
    """Print a single secret value to stdout. For scripting only."""
    value = get_secret(args.key, service=args.service)
    if value is None:
        print(f"NOT SET: {args.service}/{args.key}", file=sys.stderr)
        return 1
    print(value)
    return 0


def _cli_list(_args: argparse.Namespace) -> int:
    """Show the active backend (never reveals secret values)."""
    info = backend_info()
    print(f"keyring backend: {info['name']}")
    print(f"keyring class:   {info['class']}")
    return 0


def _cli_delete(args: argparse.Namespace) -> int:
    try:
        delete_secret(args.key, service=args.service)
        print(f"deleted: {args.service}/{args.key}")
        return 0
    except keyring.errors.PasswordDeleteError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m automatic_openconnect.secrets",
        description="Manage VPN credentials in the OS keyring (openconnect-sso namespace).",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    set_p = sub.add_parser("set", help="Interactively set VPN login PW + TOTP seed.")
    set_p.add_argument("--email", default=None,
                       help="Email address used as the keyring key.")
    set_p.set_defaults(func=_cli_set)

    get_p = sub.add_parser("get", help="Fetch a single secret (for scripting).")
    get_p.add_argument("key")
    get_p.add_argument("--service", default=SERVICE_VPN,
                       help=f"Service name (default: {SERVICE_VPN}).")
    get_p.set_defaults(func=_cli_get)

    del_p = sub.add_parser("delete", help="Remove a secret.")
    del_p.add_argument("key")
    del_p.add_argument("--service", default=SERVICE_VPN)
    del_p.set_defaults(func=_cli_delete)

    list_p = sub.add_parser("list", help="Show the active keyring backend.")
    list_p.set_defaults(func=_cli_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
