# tests/test_qr.py
# -*- coding: utf-8 -*-
"""Tests for otpauth-URI secret extraction (no OpenCV needed)."""

import base64
import unittest
from urllib.parse import quote

from automatic_openconnect import qr


def _migration_uri(secret: bytes, otype: int = 2) -> str:
    """Build a Google-Authenticator otpauth-migration:// URI containing one
    OtpParameters{secret, type}. Mirrors the real protobuf wire format."""
    otp = bytes([0x0A, len(secret)]) + secret      # field 1 (secret, bytes)
    otp += bytes([0x30, otype])                     # field 6 (type, varint)
    payload = bytes([0x0A, len(otp)]) + otp         # field 1 (otp_parameters)
    data = base64.b64encode(payload).decode("ascii")
    return "otpauth-migration://offline?data=" + quote(data)


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

    def test_otpauth_lowercase_secret_normalised(self):
        self.assertEqual(
            qr.extract_secret_from_otpauth(
                "otpauth://totp/x?secret=jbswy3dpehpk3pxp&issuer=y"),
            "JBSWY3DPEHPK3PXP")

    def test_otpauth_hotp_also_works(self):
        self.assertEqual(
            qr.extract_secret_from_otpauth(
                "otpauth://hotp/x?secret=JBSWY3DPEHPK3PXP&counter=0"),
            "JBSWY3DPEHPK3PXP")


class TestMigration(unittest.TestCase):
    def test_google_export_single_totp(self):
        secret = b"Hello!\xde\xad\xbe\xef\x12"        # 11 raw bytes
        expected = base64.b32encode(secret).decode().rstrip("=")
        self.assertEqual(
            qr.extract_secret_from_otpauth(_migration_uri(secret, otype=2)),
            expected)

    def test_migration_url_encoded_data_survives(self):
        # base64 with '+'/'/' must survive (no parse_qs '+'->space mangling)
        secret = bytes(range(20))
        out = qr.extract_secret_from_otpauth(_migration_uri(secret))
        self.assertEqual(out, base64.b32encode(secret).decode().rstrip("="))

    def test_migration_empty_data(self):
        self.assertEqual(
            qr.extract_secret_from_otpauth("otpauth-migration://offline?data="),
            "")
