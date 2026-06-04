# -*- coding: utf-8 -*-
"""
automatic_openconnect.totp_hotkey
=================================

A global keyboard shortcut that types the current 6-digit TOTP code into
whatever field has focus — so you can fill any 2FA prompt (the VPN portal,
a website, an SSH gateway) without opening a separate authenticator app.

Security
--------
The base32 *seed* never leaves the OS keyring. Only the rotating 6-digit
code is typed, and it is recomputed from scratch on every keypress (it is
valid for ~30 s). Nothing is logged.

Design
------
``current_totp_code`` is a pure function (no I/O, no keyboard) so it can be
unit-tested without a display or a global keyboard hook. ``TotpHotkey``
wraps ``pynput`` and is the side-effecting shell; it degrades gracefully to
a no-op when ``pynput`` is unavailable (e.g. headless CI).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

# Ctrl+Alt+P — pynput's GlobalHotKeys notation.
DEFAULT_HOTKEY = "<ctrl>+<alt>+p"

# Human-readable form for the UI.
DEFAULT_HOTKEY_LABEL = "Ctrl+Alt+P"

# Small settle time after we release the modifiers, before typing.
_RELEASE_DELAY = 0.12


def current_totp_code(seed: str) -> str:
    """Compute the current 6-digit TOTP code from a base32 *seed*.

    Raises ValueError if the seed is empty or not valid base32.
    """
    import pyotp

    cleaned = (seed or "").replace(" ", "")
    if not cleaned:
        raise ValueError("empty TOTP seed")
    # pyotp raises binascii.Error on a malformed base32 seed; surface it as
    # a ValueError so callers have one exception type to catch.
    try:
        return pyotp.TOTP(cleaned).now()
    except Exception as exc:  # noqa: BLE001 - normalise to ValueError
        raise ValueError(f"invalid TOTP seed: {exc}") from exc


class TotpHotkey:
    """Registers a global hotkey that types the current TOTP code.

    Parameters
    ----------
    get_seed:
        Called on each activation; must return the base32 seed (or
        ``""``/``None`` to do nothing). Pulled lazily so the hotkey keeps
        working after the stored seed changes.
    combo:
        pynput ``GlobalHotKeys`` combo string (default ``<ctrl>+<alt>+t``).
    """

    def __init__(self, get_seed: Callable[[], Optional[str]],
                 combo: str = DEFAULT_HOTKEY) -> None:
        self._get_seed = get_seed
        self._combo = combo
        self._listener = None

    @property
    def running(self) -> bool:
        return self._listener is not None

    def start(self) -> bool:
        """Begin listening. Returns True on success, False if pynput is
        unavailable or the listener could not be created (never raises)."""
        if self._listener is not None:
            return True
        try:
            from pynput import keyboard
        except Exception as exc:  # pragma: no cover - platform dependent
            log.warning("TOTP hotkey unavailable (pynput import failed): %s", exc)
            return False
        try:
            self._listener = keyboard.GlobalHotKeys({self._combo: self._fire})
            self._listener.start()
        except Exception as exc:  # pragma: no cover - platform dependent
            log.warning("could not register TOTP hotkey %s: %s", self._combo, exc)
            self._listener = None
            return False
        log.info("TOTP hotkey active: %s", self._combo)
        return True

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:  # pragma: no cover
                pass
            self._listener = None

    # --- internals ------------------------------------------------------

    def _fire(self) -> None:
        # Runs on pynput's listener thread. Do the actual typing on a
        # separate thread so we never block the listener while sleeping.
        threading.Thread(target=self._emit, daemon=True).start()

    def _emit(self) -> None:
        try:
            code = current_totp_code(self._get_seed() or "")
        except Exception as exc:  # noqa: BLE001 - log and bail, no secrets
            log.warning("TOTP hotkey: no code to type (%s)", exc)
            return
        try:
            from pynput.keyboard import Controller, Key
        except Exception:  # pragma: no cover
            return
        kb = Controller()
        # The hotkey fires while Ctrl+Alt are still physically held. On a
        # German layout Ctrl+Alt == AltGr, so typing digits now would yield
        # AltGr glyphs ({ [ ] } ² …) instead of numbers. Release the
        # modifiers ourselves so the OS sees them as up and the digits type
        # cleanly — even if the user is still pressing them.
        for mod in (Key.alt_gr, Key.ctrl, Key.ctrl_l, Key.ctrl_r,
                    Key.alt, Key.alt_l, Key.alt_r):
            try:
                kb.release(mod)
            except Exception:
                pass
        time.sleep(_RELEASE_DELAY)
        kb.type(code)
