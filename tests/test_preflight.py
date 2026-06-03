# tests/test_preflight.py
# -*- coding: utf-8 -*-
"""Tests for the prerequisites checker (no Qt, no real binaries/keyring)."""

import unittest
from unittest import mock

from automatic_openconnect import preflight


class TestOpenconnect(unittest.TestCase):
    def test_ok_when_path_exists(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=True):
            c = preflight.check_openconnect(r"C:\oc\openconnect.exe")
        self.assertTrue(c.ok)
        self.assertEqual(c.fix, "")

    def test_missing_gives_install_hint(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=False), \
             mock.patch("automatic_openconnect.preflight.detect_openconnect",
                        return_value=""):
            c = preflight.check_openconnect("")
        self.assertFalse(c.ok)
        self.assertIn("openconnect-gui", c.fix)


class TestOpenconnectSso(unittest.TestCase):
    def test_missing_gives_uv_hint(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=False), \
             mock.patch("automatic_openconnect.preflight.detect_openconnect_sso",
                        return_value=""):
            c = preflight.check_openconnect_sso("")
        self.assertFalse(c.ok)
        self.assertIn("uv tool install", c.fix)


class TestCredentials(unittest.TestCase):
    def test_no_email_is_not_ok(self):
        c = preflight.check_credentials(None)
        self.assertFalse(c.ok)

    def test_both_secrets_present(self):
        with mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value="pw"), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value="seed"):
            c = preflight.check_credentials("x@uni-graz.at")
        self.assertTrue(c.ok)

    def test_missing_totp_is_not_ok(self):
        with mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value="pw"), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value=None):
            c = preflight.check_credentials("x@uni-graz.at")
        self.assertFalse(c.ok)


class TestCheckAll(unittest.TestCase):
    def test_returns_four_checks_and_all_ok_helper(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=True), \
             mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value="pw"), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value="seed"):
            checks = preflight.check_all(
                email="x@uni-graz.at",
                openconnect_path=r"C:\oc\openconnect.exe",
                openconnect_sso_path=r"C:\oc\openconnect-sso.exe")
        self.assertEqual(len(checks), 4)
        self.assertTrue(preflight.all_ok(checks))
