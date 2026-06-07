# -*- coding: utf-8 -*-
"""
Tests for automatic_openconnect._darwin (macOS backend).

All subprocess calls are mocked - the tests never spawn openconnect-sso or
talk to the VPN. They verify the orchestration logic, platform safety, and the
no-op-when-disabled contract. Mirrors tests/test_linux.py.
"""

import sys
import subprocess
import unittest
from unittest import mock

# Ensure the secrets submodule is imported/cached so mock.patch can resolve
# "automatic_openconnect.secrets.*" regardless of test execution order
# (this file sorts before test_linux, which otherwise imports it first).
from automatic_openconnect import secrets  # noqa: F401
from automatic_openconnect._darwin import (
    VPNError,
    auto_vpn_session,
    is_vpn_up,
)


class TestDisabledIsNoOp(unittest.TestCase):
    def test_no_op_when_section_missing(self):
        with auto_vpn_session({}) as token:
            self.assertIsNone(token)

    def test_no_op_when_enabled_false(self):
        with auto_vpn_session({"auto_vpn": {"enabled": False}}) as token:
            self.assertIsNone(token)

    def test_no_subprocess_calls_when_disabled(self):
        with mock.patch("subprocess.run") as run:
            with auto_vpn_session({"auto_vpn": {"enabled": False}}):
                pass
            run.assert_not_called()


class TestPlatformGuard(unittest.TestCase):
    def test_raises_on_linux(self):
        with mock.patch.object(sys, "platform", "linux"):
            cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run on linux")
            self.assertIn("only supported on macOS", str(cm.exception))

    def test_raises_on_windows(self):
        with mock.patch.object(sys, "platform", "win32"):
            cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org"}}
            with self.assertRaises(VPNError):
                with auto_vpn_session(cfg):
                    self.fail("body should never run on win32")


class TestConfigValidation(unittest.TestCase):
    def test_raises_without_user_email(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run") as run:
            cfg = {"auto_vpn": {"enabled": True}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run without user_email")
            self.assertIn("user_email is required", str(cm.exception))
            run.assert_not_called()


class TestIsVpnUp(unittest.TestCase):
    def test_false_on_non_darwin(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(is_vpn_up())

    def test_true_when_pgrep_finds_match(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            self.assertTrue(is_vpn_up("univpn"))

    def test_false_when_pgrep_returns_nonzero(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=1)
            self.assertFalse(is_vpn_up("univpn"))

    def test_false_when_pgrep_missing(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            self.assertFalse(is_vpn_up())


class TestKeyringPreCheck(unittest.TestCase):
    def test_raises_when_login_pw_missing(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("automatic_openconnect._darwin.is_vpn_up",
                        return_value=False), \
             mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value=None), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value="seed"):
            cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run without keyring pw")
            self.assertIn("No login password in keyring", str(cm.exception))

    def test_raises_when_totp_seed_missing(self):
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("automatic_openconnect._darwin.is_vpn_up",
                        return_value=False), \
             mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value="pw"), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value=None):
            cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run without TOTP seed")
            self.assertIn("No TOTP base32 seed", str(cm.exception))


class TestEnabledDarwinFlow(unittest.TestCase):
    def test_already_up_skips_auth_and_teardown(self):
        cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org",
                            "down_on_exit": True}}
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)  # is_vpn_up -> True
            with auto_vpn_session(cfg) as token:
                self.assertTrue(token)
            for call in run.call_args_list:
                args = call.args[0] if call.args else []
                joined = " ".join(args)
                self.assertNotIn("openconnect-sso", joined)
                self.assertNotIn("sudo", joined)


class TestStartTunnel(unittest.TestCase):
    def test_uses_devnull_and_new_session(self):
        from automatic_openconnect._darwin import _start_tunnel
        with mock.patch("automatic_openconnect._darwin._resolve_tool",
                        return_value="/opt/homebrew/bin/openconnect"), \
             mock.patch("automatic_openconnect._darwin.subprocess.run") as run, \
             mock.patch("automatic_openconnect._darwin._pid_alive",
                        return_value=True), \
             mock.patch("builtins.open", mock.mock_open(read_data="12345")), \
             mock.patch("automatic_openconnect._darwin.time.sleep"):
            run.return_value = mock.Mock(returncode=0)
            _start_tunnel("host", "cookie", "fp", {"pid_file": "/tmp/oc.pid"})
            first = run.call_args_list[0]
            self.assertEqual(first.kwargs.get("stdin"), subprocess.DEVNULL)
            self.assertEqual(first.kwargs.get("stdout"), subprocess.DEVNULL)
            self.assertEqual(first.kwargs.get("stderr"), subprocess.DEVNULL)
            self.assertTrue(first.kwargs.get("start_new_session"))
            self.assertFalse(first.kwargs.get("capture_output"))

    def test_raises_when_pid_never_alive(self):
        from automatic_openconnect._darwin import _start_tunnel
        with mock.patch("automatic_openconnect._darwin._resolve_tool",
                        return_value="/opt/homebrew/bin/openconnect"), \
             mock.patch("automatic_openconnect._darwin.subprocess.run") as run, \
             mock.patch("builtins.open", side_effect=FileNotFoundError()), \
             mock.patch("automatic_openconnect._darwin.time.sleep"):
            run.return_value = mock.Mock(returncode=0)
            with self.assertRaises(VPNError) as cm:
                _start_tunnel("h", "c", "fp", {"pid_file": "/tmp/oc.pid"})
            self.assertIn("did not register a running PID", str(cm.exception))


class TestCleanupOnSetupFailure(unittest.TestCase):
    def test_stop_tunnel_called_when_start_tunnel_raises(self):
        cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org"}}
        with mock.patch.object(sys, "platform", "darwin"), \
             mock.patch("automatic_openconnect._darwin.is_vpn_up",
                        return_value=False), \
             mock.patch("automatic_openconnect._darwin._check_keyring_credentials"), \
             mock.patch("automatic_openconnect._darwin._authenticate",
                        return_value=("host", "cookie", "fp")), \
             mock.patch("automatic_openconnect._darwin._start_tunnel",
                        side_effect=VPNError("simulated")), \
             mock.patch("automatic_openconnect._darwin._stop_tunnel") as stop:
            with self.assertRaises(VPNError):
                with auto_vpn_session(cfg):
                    self.fail("body must never run when setup failed")
            stop.assert_called_once()
            self.assertEqual(stop.call_args.args[0], "univpn")


if __name__ == "__main__":
    unittest.main()
