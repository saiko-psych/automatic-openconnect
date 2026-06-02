# -*- coding: utf-8 -*-
"""
automatic_openconnect.core
==========================

Shared, platform-independent pieces for the VPN backends.

For now this is just the common exception type. The per-OS modules
(``_linux``, ``_windows``, ``_macos``) all import :class:`VPNError` from
here so a caller can write a single ``except VPNError:`` regardless of
which platform actually brought the tunnel up.
"""

from __future__ import annotations


class VPNError(RuntimeError):
    """The VPN tunnel could not be established (or torn down).

    Raised by every backend. The caller decides whether to abort the run
    or continue without the tunnel.
    """
