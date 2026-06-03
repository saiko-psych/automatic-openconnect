# tests/test_qr.py
# -*- coding: utf-8 -*-
"""Tests for otpauth-URI secret extraction (no OpenCV needed)."""

import unittest

from automatic_openconnect import qr


class TestExtractSecret(unittest.TestCase):
    def test_otpauth_uri(self):
        uri = ("otpauth://totp/Uni%20Graz:david@uni-graz.at"
               "?secret=JBSWY3DPEHPK3PXP&issuer=Uni%20Graz&digits=6")
        self.assertEqual(qr.extract_secret_from_otpauth(uri), "JBSWY3DPEHPK3PXP")

    def test_bare_base32(self):
        self.assertEqual(qr.extract_secret_from_otpauth("jbswy3dpehpk3pxp"),
                         "JBSWY3DPEHPK3PXP")

    def test_bare_base32_with_spaces(self):
        self.assertEqual(
            qr.extract_secret_from_otpauth("JBSW Y3DP EHPK 3PXP"),
            "JBSWY3DPEHPK3PXP")

    def test_non_base32_text_is_rejected(self):
        self.assertEqual(qr.extract_secret_from_otpauth("https://example.com"),
                         "")

    def test_empty(self):
        self.assertEqual(qr.extract_secret_from_otpauth(""), "")

    def test_otpauth_without_secret(self):
        self.assertEqual(
            qr.extract_secret_from_otpauth("otpauth://totp/x?issuer=y"), "")
