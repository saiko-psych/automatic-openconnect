# tests/test_gui_lifecycle.py
# -*- coding: utf-8 -*-
"""Headless (offscreen Qt) tests for the connection-lifecycle GUI changes:
single-instance guard, the off-UI-thread watchdog heartbeat, and the
close/quit exit-action handling. Run with the offscreen platform so no real
window/tray is needed.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pathlib
import tempfile
import threading
import time
import unittest
from unittest import mock

import pytest

try:
    from PyQt6.QtWidgets import QApplication
    import automatic_openconnect.gui as gui
except Exception:  # PyQt6 not installed (e.g. a headless CI without GUI deps)
    pytest.skip("PyQt6 not available", allow_module_level=True)

# One QApplication for the whole module (Qt requires it before any QWidget).
_APP = QApplication.instance() or QApplication([])


class TestSingleInstance(unittest.TestCase):
    """The 'VPN opens twice' fix: only the first instance owns the socket."""

    def test_second_instance_is_rejected(self):
        orig = gui._SINGLE_INSTANCE_NAME
        gui._SINGLE_INSTANCE_NAME = f"aoc-test-{id(self)}"
        self.addCleanup(setattr, gui, "_SINGLE_INSTANCE_NAME", orig)
        server = gui._single_instance_server(_APP)
        self.addCleanup(lambda: server.close() if server else None)
        self.assertTrue(server)                       # we became primary
        # A second launch detects the primary and bows out (caller exits).
        self.assertIsNone(gui._single_instance_server(_APP))


class TestHeartbeatThread(unittest.TestCase):
    """The heartbeat must run on its own daemon thread (off the UI thread)."""

    def setUp(self):
        self.hb = mock.patch(
            "automatic_openconnect.gui.session.write_heartbeat").start()
        mock.patch("automatic_openconnect.gui.is_vpn_up",
                   return_value=False).start()
        self.addCleanup(mock.patch.stopall)
        self.cv = gui.ControlView(on_settings=lambda: None,
                                  on_app_settings=lambda: None)
        self.cv._timer.stop()      # silence the UI refresh timer for the test
        self.addCleanup(self.cv.deleteLater)

    def test_start_keeps_writing_then_stop(self):
        self.assertFalse(self.cv._owns_session())
        self.cv._start_heartbeat()
        self.assertTrue(self.cv._owns_session())
        time.sleep(3.4)            # immediate write + ≥1 loop write (3s tick)
        self.cv._stop_heartbeat()
        self.assertFalse(self.cv._owns_session())
        self.assertGreaterEqual(self.hb.call_count, 2)
        # every heartbeat is a live (background_ok=False) write
        for call in self.hb.call_args_list:
            self.assertIs(call.kwargs.get("background_ok"), False)


class _ExitBase(unittest.TestCase):
    def setUp(self):
        self.run_ = mock.patch("automatic_openconnect.gui.tw.run").start()
        self.end_ = mock.patch("automatic_openconnect.gui.tw.end").start()
        self.hb = mock.patch(
            "automatic_openconnect.gui.session.write_heartbeat").start()
        self.clear = mock.patch(
            "automatic_openconnect.gui.session.clear").start()
        mock.patch("automatic_openconnect.gui.is_vpn_up",
                   return_value=False).start()
        self.addCleanup(mock.patch.stopall)
        self.win = gui.MainWindow()
        self.win.control._timer.stop()
        self.addCleanup(self.win.deleteLater)


class TestTeardownForExit(_ExitBase):
    """The shared teardown that close/quit use."""

    def test_background_keeps_tunnel_and_marks_background_ok(self):
        self.win._teardown_for_exit("background", live=True)
        self.run_.assert_not_called()            # tunnel NOT torn down
        self.clear.assert_not_called()
        self.hb.assert_called_once()
        self.assertIs(self.hb.call_args.kwargs.get("background_ok"), True)

    def test_disconnect_when_live_tears_down(self):
        self.win._teardown_for_exit("disconnect", live=True)
        self.run_.assert_called_once_with(gui.tw.TASK_DOWN)
        self.end_.assert_called_once_with(gui.tw.TASK_UP)
        self.clear.assert_called_once()

    def test_disconnect_when_not_live_does_not_fire_down(self):
        self.win._teardown_for_exit("disconnect", live=False)
        self.run_.assert_not_called()            # nothing to tear down
        self.clear.assert_called_once()


class TestResolveExitAction(_ExitBase):
    def test_uses_setting_when_not_asking(self):
        with mock.patch("automatic_openconnect.gui.cfgmod.load_config",
                        return_value={"ui": {"ask_on_close": False,
                                             "close_action": "background"}}):
            self.assertEqual(self.win._resolve_exit_action(), "background")


class TestCloseEvent(_ExitBase):
    """Closing the window honours the exit setting (the v0.1.20 fix)."""

    def test_close_with_disconnect_tears_down_and_quits(self):
        from PyQt6.QtGui import QCloseEvent
        gui.is_vpn_up.return_value = True            # a live tunnel
        ev = QCloseEvent()
        with mock.patch("automatic_openconnect.gui.cfgmod.load_config",
                        return_value={"ui": {"ask_on_close": False,
                                             "close_action": "disconnect"}}), \
             mock.patch.object(gui.QApplication, "instance") as inst:
            inst.return_value = mock.Mock()
            self.win.closeEvent(ev)
            inst.return_value.quit.assert_called_once()   # the app exits
        self.run_.assert_called_once_with(gui.tw.TASK_DOWN)  # tunnel torn down
        self.assertTrue(ev.isAccepted())


class TestDisconnectingStatus(unittest.TestCase):
    """Clicking Disconnect shows 'Disconnecting …' while the teardown runs,
    instead of freezing and jumping straight to 'Disconnected'."""

    def setUp(self):
        mock.patch("automatic_openconnect.gui.is_vpn_up",
                   return_value=True).start()
        mock.patch("automatic_openconnect.gui.session.write_heartbeat").start()
        mock.patch("automatic_openconnect.gui.session.clear").start()
        self.addCleanup(mock.patch.stopall)
        self.cv = gui.ControlView(on_settings=lambda: None,
                                  on_app_settings=lambda: None)
        self.cv._timer.stop()
        self.addCleanup(self.cv.deleteLater)

    def test_shows_disconnecting_during_teardown(self):
        gate = threading.Event()
        with mock.patch("automatic_openconnect.gui.tw.run",
                        side_effect=lambda *a, **k: gate.wait(5)) as run, \
             mock.patch("automatic_openconnect.gui.tw.end") as end:
            self.cv._disconnect()
            # Synchronous: status flips to "Disconnecting …" before the teardown
            # (still blocked on the gate) can finish.
            self.assertTrue(self.cv._disconnecting)
            self.assertEqual(self.cv.status.text(),
                             gui.t("status.disconnecting"))
            self.assertFalse(self.cv.disconnect_btn.isEnabled())
            gate.set()                       # let the teardown thread finish
            for _ in range(60):
                if not self.cv._disconnecting:
                    break
                time.sleep(0.05)
            self.assertFalse(self.cv._disconnecting)
            run.assert_called_once_with(gui.tw.TASK_DOWN)
            end.assert_called_once_with(gui.tw.TASK_UP)


class TestStaleConnectLogGuard(unittest.TestCase):
    """The recurring 'shows error for a moment, then connects' fix: the GUI
    can't truncate the elevated up-task's connect log, so right after Connect
    the file still holds the PREVIOUS attempt's lines. A stale 'FAIL:' there
    must NOT flash 'connection failed' — only a 'FAIL:' written for the CURRENT
    attempt (log mtime >= the click time) counts."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.gettempdir()) / f"aoc-clog-{id(self)}.log"
        self.tmp.write_text(
            "[auto_vpn_win] CLI mode: bringing tunnel up\n"
            "[auto_vpn_win] FAIL: openconnect-sso failed (exit 1).\n",
            encoding="utf-8")
        self.addCleanup(lambda: self.tmp.unlink(missing_ok=True))
        mock.patch("automatic_openconnect.gui.connect_log_path",
                   return_value=str(self.tmp)).start()
        mock.patch("automatic_openconnect.gui.is_vpn_up",
                   return_value=False).start()
        self.addCleanup(mock.patch.stopall)
        self.cv = gui.ControlView(on_settings=lambda: None,
                                  on_app_settings=lambda: None)
        self.cv._timer.stop()
        self.addCleanup(self.cv.deleteLater)

    def test_stale_fail_shows_preparing_not_failed(self):
        old = time.time() - 100
        os.utime(self.tmp, (old, old))          # log is from BEFORE the click
        self.cv._connect_t = time.time()
        self.cv._connecting = 35
        self.cv._failed = False
        self.cv.refresh()
        self.assertFalse(self.cv._failed)       # no spurious failure
        self.assertEqual(self.cv.status.text(), gui.t("step.preparing"))

    def test_fresh_fail_shows_failed(self):
        self.cv._connect_t = time.time() - 1
        os.utime(self.tmp, None)                 # log written AFTER the click
        self.cv._connecting = 35
        self.cv._failed = False
        self.cv.refresh()
        self.assertTrue(self.cv._failed)         # real, current-attempt failure
        self.assertEqual(self.cv.status.text(), gui.t("status.failed_log"))


if __name__ == "__main__":
    unittest.main()
