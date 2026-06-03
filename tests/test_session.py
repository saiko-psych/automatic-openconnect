# tests/test_session.py
# -*- coding: utf-8 -*-
"""Tests for the GUI-ownership watchdog logic (no Qt, no real files)."""

import unittest
from unittest import mock

from automatic_openconnect import session


def _patch_state(state):
    return mock.patch("automatic_openconnect.session.read_state",
                      return_value=state)


class TestShouldTeardown(unittest.TestCase):
    def test_no_session_means_leave_alone(self):
        with _patch_state({}):
            self.assertFalse(session.should_teardown(1000.0))

    def test_background_ok_is_never_torn_down(self):
        with _patch_state({"ts": 0.0, "background_ok": True}):
            self.assertFalse(session.should_teardown(1_000_000.0))

    def test_fresh_heartbeat_is_kept(self):
        with _patch_state({"ts": 995.0, "background_ok": False}):
            self.assertFalse(session.should_teardown(1000.0, stale_seconds=15))

    def test_stale_heartbeat_triggers_teardown(self):
        with _patch_state({"ts": 900.0, "background_ok": False}):
            self.assertTrue(session.should_teardown(1000.0, stale_seconds=15))

    def test_malformed_ts_is_safe(self):
        with _patch_state({"ts": "oops", "background_ok": False}):
            self.assertFalse(session.should_teardown(1000.0))


class TestRoundTrip(unittest.TestCase):
    def test_write_then_read(self):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        with mock.patch("automatic_openconnect.session.state_path",
                        return_value=d / "session.json"):
            session.write_heartbeat(123.5, background_ok=True)
            st = session.read_state()
            self.assertEqual(st["ts"], 123.5)
            self.assertTrue(st["background_ok"])
            session.clear()
            self.assertEqual(session.read_state(), {})
