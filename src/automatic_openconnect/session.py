# src/automatic_openconnect/session.py
# -*- coding: utf-8 -*-
"""GUI-ownership tracking so the elevated up-task can tear the tunnel down
if the GUI dies unexpectedly (crash / hard kill), while still allowing the
user to intentionally keep the tunnel running in the background.

A tiny JSON state file in the machine-wide config dir (C:\\ProgramData),
written by the GUI and read by the up-task — both see ProgramData
identically, unlike per-user AppData.

Contract:
- While the GUI is alive AND owns the connection, it writes a fresh
  heartbeat every few seconds with ``background_ok = False``.
- When the user closes the app and chooses "keep running in background",
  the GUI writes ``background_ok = True`` as its final write.
- The up-task loop calls :func:`should_teardown` periodically. It returns
  True only when a GUI session was recorded, did NOT opt into background
  operation, and the heartbeat has gone stale — i.e. the GUI crashed.
- If no session file exists at all (e.g. the tunnel was started from the
  CLI without the GUI), the watchdog stays out of the way.

No Qt import here, so the logic is unit-testable.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import config_dir

HEARTBEAT_STALE_SECONDS = 15.0


def state_path() -> Path:
    return config_dir() / "session.json"


def write_heartbeat(now: float, background_ok: bool = False) -> None:
    """Record a GUI heartbeat (best-effort)."""
    p = state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps({"ts": float(now), "background_ok": bool(background_ok)}),
            encoding="utf-8",
        )
    except OSError:
        pass


def read_state() -> dict:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def should_teardown(now: float,
                    stale_seconds: float = HEARTBEAT_STALE_SECONDS) -> bool:
    """True iff a GUI session exists, did not opt into background operation,
    and its heartbeat is stale (the GUI crashed or was killed)."""
    st = read_state()
    if not st:
        return False                       # no GUI session — leave it alone
    if st.get("background_ok"):
        return False                       # user kept it in background on purpose
    ts = st.get("ts")
    if not isinstance(ts, (int, float)):
        return False
    return (now - ts) > stale_seconds


def clear() -> None:
    """Remove the session file (clean disconnect / no active session)."""
    try:
        state_path().unlink()
    except OSError:
        pass
