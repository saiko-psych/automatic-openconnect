# -*- coding: utf-8 -*-
"""
automatic-openconnect
=====================

Cross-platform headless openconnect-sso automation, extracted from the
Termino project. Brings a Uni-Graz (or any Cisco AnyConnect compatible)
VPN tunnel up around a block of code, pulling the login password and TOTP
seed from the OS keyring.

USE AT YOUR OWN RISK. This is a community tool. It is NOT supported by
uniIT or any other institution.

Public API
----------
    from automatic_openconnect import auto_vpn_session, VPNError

    with auto_vpn_session(config_data):
        ...  # webmail.uni-graz.at etc. reachable inside this block

``auto_vpn_session`` is the cross-platform factory: it selects the Linux,
Windows, or macOS backend automatically and is a no-op (yields ``None``)
when ``config_data['auto_vpn'].enabled`` is not true.
"""

from __future__ import annotations

from .core import VPNError
from .factory import auto_vpn_session, make_vpn_session

__version__ = "0.1.6"
__all__ = ["auto_vpn_session", "make_vpn_session", "VPNError", "__version__"]
