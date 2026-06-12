# tests/test_posix_tray.py
# -*- coding: utf-8 -*-
"""Linux/macOS tray: the TOTP-hotkey wiring (the seed lookup + the enable
setting). The hotkey itself is pynput (already covered by test_totp_hotkey);
here we verify the tray-side glue without building a real tray."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest import mock

import pytest

try:
    import automatic_openconnect._posix_tray as t
except Exception:  # PyQt6 not installed (headless CI without GUI deps)
    pytest.skip("PyQt6 not available", allow_module_level=True)


class TestPosixHotkeyHelpers(unittest.TestCase):
    def test_enabled_defaults_true(self):
        with mock.patch.object(t.cfgmod, "load_config", return_value={}):
            self.assertTrue(t._hotkey_enabled())

    def test_enabled_respects_config(self):
        with mock.patch.object(t.cfgmod, "load_config",
                               return_value={"ui": {"totp_hotkey": False}}):
            self.assertFalse(t._hotkey_enabled())

    def test_set_enabled_persists(self):
        store = {}
        with mock.patch.object(t.cfgmod, "load_config", return_value=store), \
             mock.patch.object(t.cfgmod, "save_config") as save:
            t._set_hotkey_enabled(False)
            save.assert_called_once()
            self.assertIs(save.call_args[0][0]["ui"]["totp_hotkey"], False)

    def test_seed_read_from_keyring(self):
        with mock.patch.object(t, "_vpn_cfg",
                               return_value={"user_email": "a@b.org"}), \
             mock.patch("keyring.get_password", return_value="SEED") as gp:
            self.assertEqual(t._hotkey_seed(), "SEED")
            gp.assert_called_once_with(t.SSO_KEYRING, "totp/a@b.org")

    def test_seed_none_without_email(self):
        with mock.patch.object(t, "_vpn_cfg", return_value={}):
            self.assertIsNone(t._hotkey_seed())

    def test_seed_swallows_keyring_errors(self):
        with mock.patch.object(t, "_vpn_cfg",
                               return_value={"user_email": "a@b.org"}), \
             mock.patch("keyring.get_password", side_effect=RuntimeError("locked")):
            self.assertIsNone(t._hotkey_seed())


if __name__ == "__main__":
    unittest.main()
