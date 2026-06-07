# tests/test_gui_logic.py
# -*- coding: utf-8 -*-
"""Tests for automatic_openconnect.gui_logic (no Qt import)."""

import unittest
from unittest import mock

from automatic_openconnect import gui_logic as gl


class TestChooseView(unittest.TestCase):
    def test_setup_when_not_configured(self):
        self.assertEqual(gl.choose_view({}, registered=True), "setup")

    def test_setup_when_not_registered(self):
        cfg = {"auto_vpn": {"user_email": "x@uni-graz.at", "server": "s"}}
        self.assertEqual(gl.choose_view(cfg, registered=False), "setup")

    def test_control_when_configured_and_registered(self):
        cfg = {"auto_vpn": {"user_email": "x@uni-graz.at", "server": "s"}}
        self.assertEqual(gl.choose_view(cfg, registered=True), "control")


class TestValidateSetupForm(unittest.TestCase):
    def _ok_fields(self):
        return {"email": "x@uni-graz.at", "server": "univpn.uni-graz.at",
                "openconnect_path": r"C:\oc\openconnect.exe",
                "openconnect_sso_path": r"C:\oc\openconnect-sso.exe"}

    def test_no_errors_for_valid(self):
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=True):
            self.assertEqual(gl.validate_setup_form(self._ok_fields()), [])

    def test_error_when_email_blank(self):
        f = self._ok_fields(); f["email"] = ""
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=True):
            errs = gl.validate_setup_form(f)
        self.assertTrue(any("mail" in e.lower() for e in errs))

    def test_missing_paths_do_not_block_saving(self):
        # Tools are checked by the prerequisites dialog, not here — so a
        # missing/empty path must NOT block saving (else you get stuck on a
        # stale path you can't change).
        f = self._ok_fields()
        f["openconnect_path"] = ""
        f["openconnect_sso_path"] = r"C:\does\not\exist.exe"
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=False):
            self.assertEqual(gl.validate_setup_form(f), [])

    def test_error_when_email_whitespace_only(self):
        f = self._ok_fields(); f["email"] = "   "
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=True):
            errs = gl.validate_setup_form(f)
        self.assertTrue(any("mail" in e.lower() for e in errs))


class TestBuildAutoVpnConfig(unittest.TestCase):
    def test_builds_enabled_block(self):
        cfg = gl.build_auto_vpn_config(
            email="x@uni-graz.at", server="univpn.uni-graz.at",
            openconnect_path=r"C:\a", openconnect_sso_path=r"C:\b",
            stop_conflicting=True, conflicting_services=["csc_vpnagent"])
        av = cfg["auto_vpn"]
        self.assertTrue(av["enabled"])
        self.assertEqual(av["user_email"], "x@uni-graz.at")
        self.assertEqual(av["server"], "univpn.uni-graz.at")
        self.assertTrue(av["stop_conflicting_services"])
        self.assertEqual(av["conflicting_services"], ["csc_vpnagent"])
        self.assertTrue(av["down_on_exit"])

    def test_default_services_when_omitted(self):
        cfg = gl.build_auto_vpn_config(
            email="x", server="s", openconnect_path="a",
            openconnect_sso_path="b")
        self.assertIn("csc_vpnagent", cfg["auto_vpn"]["conflicting_services"])

    def test_explicit_empty_list_is_preserved(self):
        # BUG: removing all services then saving must persist an empty list,
        # NOT silently fall back to the defaults (the `is not None` guard).
        cfg = gl.build_auto_vpn_config(
            email="x", server="s", openconnect_path="a",
            openconnect_sso_path="b", conflicting_services=[])
        self.assertEqual(cfg["auto_vpn"]["conflicting_services"], [])


class TestParseServices(unittest.TestCase):
    def test_comma_and_space(self):
        self.assertEqual(gl.parse_services("csc_vpnagent, MullvadVPN  Foo"),
                         ["csc_vpnagent", "MullvadVPN", "Foo"])

    def test_empty(self):
        self.assertEqual(gl.parse_services("  "), [])


class TestConnectStepLabel(unittest.TestCase):
    def test_empty_log_is_generic(self):
        self.assertEqual(gl.connect_step_label(""), "step.connecting")

    def test_auth_stage(self):
        self.assertEqual(
            gl.connect_step_label("[auto_vpn_win] Authenticating via openconnect-sso ..."),
            "step.signing_in")

    def test_tunnel_stage(self):
        log = ("Authenticating via openconnect-sso ...\n"
               "[auto_vpn_win] Starting openconnect.exe ...")
        self.assertEqual(gl.connect_step_label(log), "step.tunnel")

    def test_almost_done(self):
        self.assertEqual(
            gl.connect_step_label("Legacy IP route configuration done."),
            "step.almost")

    def test_failure_takes_priority(self):
        log = ("Starting openconnect.exe ...\n"
               "Traceback (most recent call last):\n  ...")
        self.assertEqual(gl.connect_step_label(log), "step.failed")


class TestDetect(unittest.TestCase):
    def test_detect_openconnect_prefers_standard_path(self):
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=True):
            self.assertTrue(gl.detect_openconnect().endswith("openconnect.exe"))

    def test_detect_openconnect_falls_back_to_which(self):
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=False), \
             mock.patch("automatic_openconnect.gui_logic.shutil.which",
                        return_value=r"C:\fallback\openconnect.exe"):
            self.assertEqual(gl.detect_openconnect(), r"C:\fallback\openconnect.exe")

    def test_detect_openconnect_sso_falls_back_to_which(self):
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=False), \
             mock.patch("automatic_openconnect.gui_logic.shutil.which", return_value=r"C:\x\openconnect-sso.exe"):
            self.assertEqual(gl.detect_openconnect_sso(),
                             r"C:\x\openconnect-sso.exe")

    def test_detect_openconnect_finds_program_files_x86(self):
        x86 = r"C:\Program Files (x86)\OpenConnect-GUI\openconnect.exe"
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists",
                        side_effect=lambda p: p == x86):
            self.assertEqual(gl.detect_openconnect(), x86)

    def test_detect_sso_falls_back_to_user_tool_bin(self):
        with mock.patch("automatic_openconnect.gui_logic.shutil.which",
                        return_value=None), \
             mock.patch("automatic_openconnect.gui_logic.os.path.exists",
                        side_effect=lambda p: p.endswith("openconnect-sso.exe")):
            self.assertTrue(
                gl.detect_openconnect_sso().endswith("openconnect-sso.exe"))


class TestNormalizeOpenconnectPath(unittest.TestCase):
    CLI = r"C:\Program Files\OpenConnect-GUI\openconnect.exe"

    def test_gui_exe_becomes_cli(self):
        gui = r"C:\Program Files\OpenConnect-GUI\openconnect-gui.exe"
        with mock.patch("os.path.isdir", return_value=False), \
             mock.patch("os.path.isfile", side_effect=lambda p: p == self.CLI):
            self.assertEqual(gl.normalize_openconnect_path(gui), self.CLI)

    def test_directory_becomes_cli_inside(self):
        d = r"C:\Program Files\OpenConnect-GUI"
        with mock.patch("os.path.isdir", side_effect=lambda p: p == d), \
             mock.patch("os.path.isfile", side_effect=lambda p: p == self.CLI):
            self.assertEqual(gl.normalize_openconnect_path(d), self.CLI)

    def test_plain_openconnect_unchanged(self):
        with mock.patch("os.path.isdir", return_value=False), \
             mock.patch("os.path.isfile", side_effect=lambda p: p == self.CLI):
            self.assertEqual(gl.normalize_openconnect_path(self.CLI), self.CLI)

    def test_bogus_path_falls_back_to_detection(self):
        detected = r"C:\detected\openconnect.exe"
        with mock.patch("os.path.isdir", return_value=False), \
             mock.patch("os.path.isfile", return_value=False), \
             mock.patch("automatic_openconnect.gui_logic.detect_openconnect",
                        return_value=detected):
            self.assertEqual(gl.normalize_openconnect_path(r"C:\bad\x.exe"),
                             detected)


class TestResolveUv(unittest.TestCase):
    def test_uses_uv_on_path(self):
        with mock.patch("automatic_openconnect.gui_logic.shutil.which",
                        return_value=r"C:\bin\uv.exe"):
            self.assertEqual(gl.resolve_uv(), [r"C:\bin\uv.exe"])

    def test_finds_uv_in_user_tool_bin(self):
        with mock.patch("automatic_openconnect.gui_logic.shutil.which",
                        return_value=None), \
             mock.patch("automatic_openconnect.gui_logic.os.path.exists",
                        side_effect=lambda p: p.endswith("uv.exe")):
            r = gl.resolve_uv()
        self.assertEqual(len(r), 1)
        self.assertTrue(r[0].endswith("uv.exe"))

    def test_empty_when_uv_absent_and_no_python(self):
        with mock.patch("automatic_openconnect.gui_logic.shutil.which",
                        return_value=None), \
             mock.patch("automatic_openconnect.gui_logic.os.path.exists",
                        return_value=False):
            self.assertEqual(gl.resolve_uv(), [])
