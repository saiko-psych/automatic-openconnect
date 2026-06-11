# -*- coding: utf-8 -*-
"""
Tests for automatic_openconnect._windows.

All subprocess and ctypes calls are mocked - these tests run cleanly
on Linux CI and never spawn openconnect-sso, openconnect.exe, or talk
to univpn.uni-graz.at. They verify the orchestration logic, platform
guards, and the no-op-when-disabled contract.
"""

import pathlib
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

# We import the module under test from a Linux CI environment. The
# top-level import path is fine because the module's platform-specific
# behavior is gated behind sys.platform checks inside each function -
# no Windows-only modules are imported at module load time.
from automatic_openconnect._windows import (
    auto_vpn_session_win,
    is_vpn_up,
    _build_cli_parser,
    _cli_down,
    _WinVpnSession,
)
from automatic_openconnect._linux import VPNError


# --- no-op when disabled -------------------------------------------------

class TestDisabledIsNoOp(unittest.TestCase):
    """When auto_vpn is not enabled, the context manager does nothing."""

    def test_no_op_when_section_missing(self):
        with auto_vpn_session_win({}) as token:
            self.assertIsNone(token)

    def test_no_op_when_enabled_false(self):
        cfg = {"auto_vpn": {"enabled": False}}
        with auto_vpn_session_win(cfg) as token:
            self.assertIsNone(token)

    def test_no_op_when_section_is_none(self):
        with auto_vpn_session_win({"auto_vpn": None}) as token:
            self.assertIsNone(token)

    def test_no_subprocess_calls_when_disabled(self):
        with mock.patch("subprocess.run") as run:
            with auto_vpn_session_win({"auto_vpn": {"enabled": False}}):
                pass
            run.assert_not_called()


# --- platform guard ------------------------------------------------------

class TestPlatformGuard(unittest.TestCase):
    """auto_vpn_win refuses to act on non-Windows."""

    def test_raises_on_linux(self):
        with mock.patch.object(sys, "platform", "linux"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run on linux")
            self.assertIn("only supported on Windows", str(cm.exception))

    def test_raises_on_darwin(self):
        with mock.patch.object(sys, "platform", "darwin"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError):
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run on darwin")


# --- config validation --------------------------------------------------

class TestConfigValidation(unittest.TestCase):
    """Required fields are validated before any subprocess is spawned."""

    def test_raises_without_user_email(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("subprocess.run") as run:
            cfg = {"auto_vpn": {"enabled": True}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run without user_email")
            self.assertIn("user_email is required", str(cm.exception))
            run.assert_not_called()


# --- is_vpn_up probe ----------------------------------------------------

class TestIsVpnUp(unittest.TestCase):
    """tasklist-based detection, cross-platform safe."""

    def test_false_on_non_windows(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(is_vpn_up())

    def test_true_when_tasklist_finds_match(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            run.return_value = mock.Mock(
                stdout="openconnect.exe    1234 Console  1  10,000 K",
            )
            self.assertTrue(is_vpn_up())

    def test_false_when_tasklist_no_match(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            run.return_value = mock.Mock(
                stdout="INFO: No tasks are running which match the criteria.",
            )
            self.assertFalse(is_vpn_up())

    def test_false_when_tasklist_missing(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.subprocess.run",
                        side_effect=FileNotFoundError()):
            self.assertFalse(is_vpn_up())


# --- keyring pre-check ---------------------------------------------------

class TestKeyringPreCheck(unittest.TestCase):
    """Keyring is probed before openconnect-sso is spawned."""

    def test_raises_when_login_pw_missing(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run, \
             mock.patch("automatic_openconnect._windows.is_vpn_up", return_value=False), \
             mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value=None), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value="seed"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run without keyring pw")
            self.assertIn("No UGO login password", str(cm.exception))
            self.assertIn("Windows Credential Manager", str(cm.exception))

    def test_raises_when_totp_seed_missing(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run, \
             mock.patch("automatic_openconnect._windows.is_vpn_up", return_value=False), \
             mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value="some-pw"), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value=None):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run without TOTP seed")
            self.assertIn("No TOTP base32 seed", str(cm.exception))


# --- admin guard ---------------------------------------------------------

class TestAdminGuard(unittest.TestCase):
    """_start_tunnel refuses to run without Administrator privileges."""

    def test_raises_when_not_admin(self):
        from automatic_openconnect._windows import _start_tunnel
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows._is_admin", return_value=False), \
             mock.patch("automatic_openconnect._windows._resolve_tool",
                        return_value="C:/openconnect.exe"):
            with self.assertRaises(VPNError) as cm:
                _start_tunnel("host", "cookie", "fp",
                              {"openconnect_path": "C:/openconnect.exe"})
            self.assertIn("Administrator", str(cm.exception))


# --- cleanup on setup failure -------------------------------------------

class TestCleanupOnSetupFailure(unittest.TestCase):
    """If _start_tunnel raises mid-flight, conflicting services restart
    and any partial openconnect.exe gets killed."""

    def test_services_restart_when_authenticate_raises(self):
        cfg = {"auto_vpn": {"enabled": True,
                            "user_email": "x@example.org",
                            "stop_cisco_during_run": True,
                            "stop_mullvad_during_run": True}}
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.is_vpn_up", return_value=False), \
             mock.patch("automatic_openconnect._windows._check_keyring_credentials"), \
             mock.patch("automatic_openconnect._windows._stop_conflicting_services",
                        return_value=["csc_vpnagent", "MullvadVPN"]), \
             mock.patch("automatic_openconnect._windows._restart_services") as restart, \
             mock.patch("automatic_openconnect._windows._stop_tunnel_by_proc") as stop_proc, \
             mock.patch("automatic_openconnect._windows._authenticate",
                        side_effect=VPNError("simulated auth failure")):

            with self.assertRaises(VPNError):
                with auto_vpn_session_win(cfg):
                    self.fail("body must never run when setup failed")

            # We had not yet spawned a tunnel proc - but stop_proc is
            # still called with None as a belt-and-braces sweep.
            stop_proc.assert_called_once_with(None)
            # And services we stopped must be restarted.
            restart.assert_called_once_with(["csc_vpnagent", "MullvadVPN"])

    def test_services_restart_when_tunnel_raises(self):
        cfg = {"auto_vpn": {"enabled": True,
                            "user_email": "x@example.org",
                            "stop_cisco_during_run": True}}
        fake_proc = mock.Mock()
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("automatic_openconnect._windows.is_vpn_up", return_value=False), \
             mock.patch("automatic_openconnect._windows._check_keyring_credentials"), \
             mock.patch("automatic_openconnect._windows._stop_conflicting_services",
                        return_value=["csc_vpnagent"]), \
             mock.patch("automatic_openconnect._windows._restart_services") as restart, \
             mock.patch("automatic_openconnect._windows._stop_tunnel_by_proc") as stop_proc, \
             mock.patch("automatic_openconnect._windows._authenticate",
                        return_value=("host", "cookie", "fp")), \
             mock.patch("automatic_openconnect._windows._start_tunnel",
                        side_effect=VPNError("tunnel blew up")):

            with self.assertRaises(VPNError):
                with auto_vpn_session_win(cfg):
                    self.fail("body must never run")

            stop_proc.assert_called_once()
            restart.assert_called_once_with(["csc_vpnagent"])


# --- service coexistence helpers ----------------------------------------

class TestServiceCoexistence(unittest.TestCase):
    """_stop_conflicting_services only stops what's actually running and
    what config opts into."""

    def test_skips_services_already_stopped(self):
        from automatic_openconnect._windows import _stop_conflicting_services
        cfg = {"stop_cisco_during_run": True,
               "stop_mullvad_during_run": True}
        with mock.patch("automatic_openconnect._windows._service_status",
                        return_value="STOPPED"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            result = _stop_conflicting_services(cfg)
            # Nothing was running, so nothing is in our restart-list
            self.assertEqual(result, [])
            # And we never called `net stop`
            for call in run.call_args_list:
                self.assertNotIn("stop", call.args[0])

    def test_opt_out_via_config(self):
        from automatic_openconnect._windows import _stop_conflicting_services
        cfg = {"stop_cisco_during_run": False,
               "stop_mullvad_during_run": False}
        with mock.patch("automatic_openconnect._windows._service_status",
                        return_value="RUNNING"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            result = _stop_conflicting_services(cfg)
            self.assertEqual(result, [])
            run.assert_not_called()


class TestCliParser(unittest.TestCase):
    """The registered Scheduled Task passes `--config` AFTER the subcommand."""

    def test_config_after_up_subcommand(self):
        args = _build_cli_parser().parse_args(["up", "--config", r"C:\x\config.json"])
        self.assertEqual(args.cmd, "up")
        self.assertEqual(args.config, r"C:\x\config.json")

    def test_config_after_down_subcommand(self):
        args = _build_cli_parser().parse_args(["down", "--config", "c.json"])
        self.assertEqual(args.cmd, "down")
        self.assertEqual(args.config, "c.json")

    def test_up_without_config_uses_default(self):
        args = _build_cli_parser().parse_args(["up"])
        self.assertEqual(args.config, "config.json")


class TestCliDownRespectsConfig(unittest.TestCase):
    """`down` must only restart the services this app was configured to
    stop, not blindly force-start Cisco/Mullvad."""

    @staticmethod
    def _started_services(run_mock):
        """Service names passed to `net start` across all subprocess calls."""
        started = []
        for call in run_mock.call_args_list:
            argv = call.args[0] if call.args else call.kwargs.get("args", [])
            if len(argv) >= 3 and argv[0] == "net" and argv[1] == "start":
                started.append(argv[2])
        return started

    def test_no_restart_when_both_flags_false(self):
        args = _build_cli_parser().parse_args(["down", "--config", "c.json"])
        cfg = {"auto_vpn": {"stop_cisco_during_run": False,
                            "stop_mullvad_during_run": False}}
        with mock.patch("automatic_openconnect._windows._load_config",
                        return_value=cfg), \
             mock.patch("automatic_openconnect._windows._stop_tunnel_by_proc"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            self.assertEqual(_cli_down(args), 0)
            self.assertEqual(self._started_services(run), [])

    def test_restarts_only_mullvad_when_only_mullvad_opted_in(self):
        args = _build_cli_parser().parse_args(["down", "--config", "c.json"])
        cfg = {"auto_vpn": {"stop_cisco_during_run": False,
                            "stop_mullvad_during_run": True}}
        with mock.patch("automatic_openconnect._windows._load_config",
                        return_value=cfg), \
             mock.patch("automatic_openconnect._windows._stop_tunnel_by_proc"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            _cli_down(args)
            self.assertEqual(self._started_services(run), ["MullvadVPN"])

    def test_restarts_both_by_default(self):
        args = _build_cli_parser().parse_args(["down", "--config", "c.json"])
        with mock.patch("automatic_openconnect._windows._load_config",
                        return_value={"auto_vpn": {}}), \
             mock.patch("automatic_openconnect._windows._stop_tunnel_by_proc"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            _cli_down(args)
            self.assertEqual(self._started_services(run),
                             ["csc_vpnagent", "MullvadVPN"])

    def test_falls_back_to_both_when_config_unreadable(self):
        args = _build_cli_parser().parse_args(["down", "--config", "missing.json"])
        with mock.patch("automatic_openconnect._windows._load_config",
                        side_effect=FileNotFoundError()), \
             mock.patch("automatic_openconnect._windows._stop_tunnel_by_proc"), \
             mock.patch("automatic_openconnect._windows.subprocess.run") as run:
            self.assertEqual(_cli_down(args), 0)
            self.assertEqual(self._started_services(run),
                             ["csc_vpnagent", "MullvadVPN"])


class TestConfiguredServiceTargets(unittest.TestCase):
    """Generic `conflicting_services` list, with legacy back-compat."""

    def test_generic_list(self):
        from automatic_openconnect._windows import _configured_service_targets
        cfg = {"stop_conflicting_services": True,
               "conflicting_services": ["FooVPN", "BarVPN"]}
        self.assertEqual(_configured_service_targets(cfg), ["FooVPN", "BarVPN"])

    def test_generic_disabled(self):
        from automatic_openconnect._windows import _configured_service_targets
        cfg = {"stop_conflicting_services": False,
               "conflicting_services": ["FooVPN"]}
        self.assertEqual(_configured_service_targets(cfg), [])

    def test_legacy_flags_still_work(self):
        from automatic_openconnect._windows import _configured_service_targets
        cfg = {"stop_cisco_during_run": True, "stop_mullvad_during_run": False}
        self.assertEqual(_configured_service_targets(cfg), ["csc_vpnagent"])

    def test_empty_cfg_defaults_to_both(self):
        from automatic_openconnect._windows import _configured_service_targets
        self.assertEqual(_configured_service_targets({}),
                         ["csc_vpnagent", "MullvadVPN"])

    def test_explicit_empty_list_stops_nothing(self):
        # BUG: an explicitly-emptied list must mean "stop nothing", not
        # silently fall back to the Cisco/Mullvad defaults via `... or DEFAULT`.
        from automatic_openconnect._windows import _configured_service_targets
        cfg = {"stop_conflicting_services": True, "conflicting_services": []}
        self.assertEqual(_configured_service_targets(cfg), [])

    def test_explicit_empty_list_with_only_list_key(self):
        # Even if the bool flag isn't present (defaults True), an explicit []
        # must still stop nothing.
        from automatic_openconnect._windows import _configured_service_targets
        cfg = {"conflicting_services": []}
        self.assertEqual(_configured_service_targets(cfg), [])


class TestConnectLog(unittest.TestCase):
    """The connect log must never be silently empty — the GUI seeds a
    preamble, the backend appends, and open failures leave a breadcrumb."""

    def test_connect_log_path_sits_next_to_config(self):
        import ntpath
        from automatic_openconnect._windows import connect_log_path
        p = connect_log_path(ntpath.join("C:\\", "data", "config.json"))
        self.assertTrue(p.endswith("last-connect.log"))

    def test_append_connect_log_appends(self):
        import os, tempfile
        from automatic_openconnect._windows import (
            append_connect_log, connect_log_path)
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            self.assertTrue(append_connect_log(cfg, "first"))
            self.assertTrue(append_connect_log(cfg, "second"))
            with open(connect_log_path(cfg), encoding="utf-8") as f:
                body = f.read()
        self.assertEqual(body, "first\nsecond\n")

    def test_append_connect_log_truncate_starts_fresh(self):
        import os, tempfile
        from automatic_openconnect._windows import (
            append_connect_log, connect_log_path)
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            append_connect_log(cfg, "stale line from a previous attempt")
            self.assertTrue(append_connect_log(cfg, "[gui] firing",
                                               truncate=True))
            with open(connect_log_path(cfg), encoding="utf-8") as f:
                body = f.read()
        self.assertEqual(body, "[gui] firing\n")

    def test_append_connect_log_returns_false_on_oserror(self):
        from automatic_openconnect._windows import append_connect_log
        with mock.patch("automatic_openconnect._windows.open",
                        side_effect=OSError("denied")):
            self.assertFalse(append_connect_log("C:\\x\\config.json", "msg"))

    def test_redirect_failure_leaves_breadcrumb(self):
        # If even the log can't be opened, the failure must be recorded to a
        # sibling .error file (and never raise).
        import automatic_openconnect._windows as w
        calls = {}

        def fake_open(path, mode="r", *a, **k):
            if str(path).endswith("last-connect.log"):
                raise OSError("denied")
            calls["alt"] = str(path)
            import io
            return io.StringIO()

        with mock.patch("automatic_openconnect._windows.open",
                        side_effect=fake_open):
            w._redirect_output_to_log("C:\\x\\config.json")  # must not raise
        self.assertTrue(calls.get("alt", "").endswith("last-connect.error"))

    def test_cli_up_logs_first_line_before_loading_config(self):
        # The very first backend line must be written even if config loading
        # fails afterwards — so an empty log unambiguously means "never ran".
        import automatic_openconnect._windows as w
        written = []

        class Sink:
            def write(self, s):
                written.append(s)

            def flush(self):
                pass

        def fake_redirect(_path):
            sys.stdout = sys.stderr = Sink()

        args = mock.Mock(config="C:\\x\\config.json")
        saved_out, saved_err = sys.stdout, sys.stderr
        try:
            with mock.patch.object(w, "_redirect_output_to_log",
                                   side_effect=fake_redirect), \
                 mock.patch.object(w, "_load_config",
                                   side_effect=OSError("no config")):
                with self.assertRaises(OSError):
                    w._cli_up(args)
        finally:
            sys.stdout, sys.stderr = saved_out, saved_err
        self.assertTrue(any("bringing tunnel up" in s for s in written))


class TestAutoReconnect(unittest.TestCase):
    """The _WinVpnSession handle exposes alive()/reconnect() so the up-task can
    re-establish the tunnel after a network drop WITHOUT flapping services."""

    def _session(self):
        return _WinVpnSession({"user_email": "x@example.org"})

    def test_alive_false_without_proc(self):
        self.assertFalse(self._session().alive())

    def test_alive_true_while_proc_running(self):
        s = self._session()
        s.proc = mock.Mock()
        s.proc.poll.return_value = None      # still running
        self.assertTrue(s.alive())

    def test_alive_false_after_proc_exits(self):
        s = self._session()
        s.proc = mock.Mock()
        s.proc.poll.return_value = 1         # openconnect exited (network drop)
        self.assertFalse(s.alive())

    def test_reconnect_reauths_without_touching_services(self):
        s = self._session()
        s.stopped_services = ["csc_vpnagent"]
        new_proc = mock.Mock()
        with mock.patch("automatic_openconnect._windows._kill_stale_processes") as kill, \
             mock.patch("automatic_openconnect._windows._authenticate",
                        return_value=("host", "cookie", "fp")), \
             mock.patch("automatic_openconnect._windows._start_tunnel",
                        return_value=new_proc) as start, \
             mock.patch("automatic_openconnect._windows._stop_conflicting_services") as stop_svc, \
             mock.patch("automatic_openconnect._windows._restart_services") as restart:
            s.reconnect()
            kill.assert_called_once()      # clears the dead openconnect first
            start.assert_called_once()     # re-spawned the tunnel
            self.assertIs(s.proc, new_proc)
            stop_svc.assert_not_called()   # services NOT flapped on reconnect
            restart.assert_not_called()


class TestServicesMarker(unittest.TestCase):
    """Crash/logoff recovery: the app records which conflicting services it
    stopped, so a session that dies before its teardown can be recovered. The
    marker is cleared on every clean restart."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        mock.patch("automatic_openconnect.config.config_dir",
                   return_value=pathlib.Path(self.tmp)).start()
        self.addCleanup(mock.patch.stopall)
        import shutil
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_roundtrip(self):
        from automatic_openconnect import _windows as w
        self.assertEqual(w.read_services_marker(), [])
        w._mark_services_stopped(["csc_vpnagent", "MullvadVPN"])
        self.assertEqual(w.read_services_marker(), ["csc_vpnagent", "MullvadVPN"])
        w._clear_services_marker()
        self.assertEqual(w.read_services_marker(), [])

    def test_mark_empty_is_noop(self):
        from automatic_openconnect import _windows as w
        w._mark_services_stopped([])
        self.assertEqual(w.read_services_marker(), [])

    def test_start_marks_then_teardown_clears(self):
        from automatic_openconnect import _windows as w
        s = w._WinVpnSession({"user_email": "x@example.org"})
        with mock.patch.object(w, "_kill_stale_processes"), \
             mock.patch.object(w, "_check_keyring_credentials"), \
             mock.patch.object(w, "_stop_conflicting_services",
                               return_value=["MullvadVPN"]), \
             mock.patch.object(s, "_bring_up"):
            s.start()
        self.assertEqual(w.read_services_marker(), ["MullvadVPN"])  # persisted
        with mock.patch.object(w, "_stop_tunnel_by_proc"), \
             mock.patch.object(w, "_restart_services"):
            s.teardown()
        self.assertEqual(w.read_services_marker(), [])              # cleared


if __name__ == "__main__":
    unittest.main()
