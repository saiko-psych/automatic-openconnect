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

    def test_error_when_openconnect_missing(self):
        f = self._ok_fields()
        with mock.patch("automatic_openconnect.gui_logic.os.path.exists", return_value=False):
            errs = gl.validate_setup_form(f)
        self.assertTrue(any("openconnect" in e.lower() for e in errs))

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
            stop_cisco=True, stop_mullvad=False)
        av = cfg["auto_vpn"]
        self.assertTrue(av["enabled"])
        self.assertEqual(av["user_email"], "x@uni-graz.at")
        self.assertEqual(av["server"], "univpn.uni-graz.at")
        self.assertTrue(av["stop_cisco_during_run"])
        self.assertFalse(av["stop_mullvad_during_run"])
        self.assertTrue(av["down_on_exit"])


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
