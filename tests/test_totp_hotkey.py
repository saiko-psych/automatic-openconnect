# tests/test_totp_hotkey.py
# -*- coding: utf-8 -*-
"""Tests for the pure TOTP-code helper (no pynput / keyboard needed)."""

import unittest

import pyotp

from automatic_openconnect import totp_hotkey as th


class TestCurrentTotpCode(unittest.TestCase):
    SEED = "JBSWY3DPEHPK3PXP"  # standard pyotp example base32 seed

    def test_matches_pyotp(self):
        self.assertEqual(th.current_totp_code(self.SEED),
                         pyotp.TOTP(self.SEED).now())

    def test_is_six_digits(self):
        code = th.current_totp_code(self.SEED)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_spaces_are_stripped(self):
        spaced = "JBSW Y3DP EHPK 3PXP"
        self.assertEqual(th.current_totp_code(spaced),
                         pyotp.TOTP(self.SEED).now())

    def test_empty_seed_raises(self):
        with self.assertRaises(ValueError):
            th.current_totp_code("")
        with self.assertRaises(ValueError):
            th.current_totp_code("   ")

    def test_invalid_base32_raises_value_error(self):
        # '1' and '0' are not valid base32 alphabet characters.
        with self.assertRaises(ValueError):
            th.current_totp_code("10101010")


class TestTotpHotkeyDegradesGracefully(unittest.TestCase):
    def test_constructs_without_pynput(self):
        # Constructing must not import pynput or touch the keyboard.
        hk = th.TotpHotkey(lambda: TestCurrentTotpCode.SEED)
        self.assertFalse(hk.running)


if __name__ == "__main__":
    unittest.main()
