# tests/test_preflight.py
# -*- coding: utf-8 -*-
"""Tests for the prerequisites checker (no Qt, no real binaries/keyring)."""

import unittest
from unittest import mock

from automatic_openconnect import preflight


class TestOpenconnect(unittest.TestCase):
    def test_ok_when_real_file(self):
        cli = r"C:\oc\openconnect.exe"
        with mock.patch("os.path.isdir", return_value=False), \
             mock.patch("os.path.isfile", side_effect=lambda p: p == cli):
            c = preflight.check_openconnect(cli)
        self.assertTrue(c.ok)
        self.assertEqual(c.fix, "")

    def test_directory_is_not_ok(self):
        # A folder (e.g. a Start-Menu shortcut dir) must NOT pass as the engine.
        d = r"C:\ProgramData\...\Start Menu\Programs\OpenConnect-GUI"
        with mock.patch("os.path.isdir", side_effect=lambda p: p == d), \
             mock.patch("os.path.isfile", return_value=False), \
             mock.patch("automatic_openconnect.gui_logic.detect_openconnect",
                        return_value=""):
            c = preflight.check_openconnect(d)
        self.assertFalse(c.ok)

    def test_missing_gives_install_hint_windows(self):
        with mock.patch.object(preflight.sys, "platform", "win32"), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("os.path.isfile", return_value=False), \
             mock.patch("automatic_openconnect.gui_logic.detect_openconnect",
                        return_value=""):
            c = preflight.check_openconnect("")
        self.assertFalse(c.ok)
        self.assertEqual(c.fix, "fix.openconnect")
        self.assertEqual(c.action, "open_download")

    def test_missing_gives_install_hint_unix(self):
        # Linux/macOS: package-manager hint, no download button.
        with mock.patch.object(preflight.sys, "platform", "linux"), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("os.path.isfile", return_value=False), \
             mock.patch("automatic_openconnect.gui_logic.detect_openconnect",
                        return_value=""):
            c = preflight.check_openconnect("")
        self.assertFalse(c.ok)
        self.assertEqual(c.fix, "fix.openconnect_unix")
        self.assertEqual(c.action, "")


class TestOpenconnectSso(unittest.TestCase):
    def test_missing_offers_uv_install(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=False), \
             mock.patch("automatic_openconnect.preflight.detect_openconnect_sso",
                        return_value=""):
            c = preflight.check_openconnect_sso("")
        self.assertFalse(c.ok)
        self.assertEqual(c.fix, "fix.sso")
        self.assertEqual(c.action, "install_sso")


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


class TestAutoFixes(unittest.TestCase):
    def test_config_check_offers_create_action(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=False):
            c = preflight.check_config_toml()
        self.assertFalse(c.ok)
        self.assertEqual(c.action, "create_config")

    def test_sso_check_offers_install_action(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=False), \
             mock.patch("automatic_openconnect.preflight.detect_openconnect_sso",
                        return_value=""):
            c = preflight.check_openconnect_sso("")
        self.assertEqual(c.action, "install_sso")

    def test_create_config_writes_template(self):
        import os as _os
        import tempfile
        target = _os.path.join(tempfile.mkdtemp(), "oc", "config.toml")
        with mock.patch("automatic_openconnect.preflight.CONFIG_TOML", target):
            p = preflight.create_config_toml()
        self.assertEqual(p, target)
        with open(target, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("univpn.uni-graz.at", content)
        self.assertIn('fill = "totp"', content)

    def test_config_toml_no_slot_by_default(self):
        toml = preflight.build_config_toml(0)
        self.assertNotIn("nth-of-type", toml)
        self.assertIn('fill = "totp"', toml)

    def test_config_toml_with_slot_clicks_tile_before_otp(self):
        toml = preflight.build_config_toml(2)
        self.assertIn("label:nth-of-type(2)", toml)
        # the tile click must come BEFORE the otp fill
        self.assertLess(toml.index("nth-of-type(2)"), toml.index('fill = "totp"'))

    def test_install_sso_command(self):
        with mock.patch("automatic_openconnect.gui_logic.resolve_uv",
                        return_value=["uv"]):
            cmd = preflight.install_sso_command()
        self.assertEqual(cmd[:3], ["uv", "tool", "install"])
        self.assertIn("openconnect-sso", cmd)

    def test_install_sso_command_empty_without_uv(self):
        with mock.patch("automatic_openconnect.gui_logic.resolve_uv",
                        return_value=[]):
            self.assertEqual(preflight.install_sso_command(), [])


class TestWintun(unittest.TestCase):
    def test_warns_when_oc_found_but_dll_missing(self):
        # openconnect resolves, but no wintun.dll anywhere → warn (not block).
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        side_effect=lambda p: p.endswith("openconnect.exe")):
            c = preflight.check_wintun(r"C:\oc\openconnect.exe")
        self.assertFalse(c.ok)
        self.assertTrue(c.warn_only)
        self.assertEqual(c.fix, "fix.wintun")

    def test_ok_when_dll_next_to_openconnect(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=True):
            c = preflight.check_wintun(r"C:\oc\openconnect.exe")
        self.assertTrue(c.ok)
        self.assertTrue(c.warn_only)

    def test_silent_when_openconnect_not_found(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=False), \
             mock.patch("automatic_openconnect.preflight.detect_openconnect",
                        return_value=""):
            c = preflight.check_wintun("")
        self.assertTrue(c.ok)        # don't double-warn; oc check handles it
        self.assertTrue(c.warn_only)


class TestAllOkIgnoresWarnings(unittest.TestCase):
    def test_warn_only_failure_does_not_block(self):
        checks = [preflight.Check("a", True),
                  preflight.Check("check.wintun", False, warn_only=True)]
        self.assertTrue(preflight.all_ok(checks))

    def test_blocking_failure_blocks(self):
        checks = [preflight.Check("a", False),
                  preflight.Check("check.wintun", True, warn_only=True)]
        self.assertFalse(preflight.all_ok(checks))


class TestCheckAll(unittest.TestCase):
    def _run_check_all(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=True), \
             mock.patch("os.path.isfile", return_value=True), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("automatic_openconnect.secrets.get_uni_login_password",
                        return_value="pw"), \
             mock.patch("automatic_openconnect.secrets.get_uni_totp_secret",
                        return_value="seed"):
            return preflight.check_all(
                email="x@uni-graz.at",
                openconnect_path=r"C:\oc\openconnect.exe",
                openconnect_sso_path=r"C:\oc\openconnect-sso.exe")

    def test_windows_includes_wintun_and_vpnc(self):
        with mock.patch.object(preflight.sys, "platform", "win32"):
            checks = self._run_check_all()
        names = [c.name for c in checks]
        self.assertEqual(len(checks), 6)
        self.assertIn("check.wintun", names)
        self.assertIn("check.vpnc", names)
        self.assertTrue(preflight.all_ok(checks))

    def test_unix_omits_windows_only_checks(self):
        # Linux/macOS: no Wintun / vpnc-script-win.js checks.
        with mock.patch.object(preflight.sys, "platform", "linux"):
            checks = self._run_check_all()
        names = [c.name for c in checks]
        self.assertEqual(len(checks), 4)
        self.assertNotIn("check.wintun", names)
        self.assertNotIn("check.vpnc", names)
        self.assertTrue(preflight.all_ok(checks))


class TestVpncScript(unittest.TestCase):
    def test_warns_when_script_missing(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        side_effect=lambda p: p.endswith("openconnect.exe")):
            c = preflight.check_vpnc_script(r"C:\dl\openconnect.exe")
        self.assertFalse(c.ok)
        self.assertTrue(c.warn_only)
        self.assertEqual(c.fix, "fix.vpnc")

    def test_ok_when_script_next_to_exe(self):
        with mock.patch("automatic_openconnect.preflight.os.path.exists",
                        return_value=True):
            c = preflight.check_vpnc_script(r"C:\oc\openconnect.exe")
        self.assertTrue(c.ok)
        self.assertTrue(c.warn_only)
