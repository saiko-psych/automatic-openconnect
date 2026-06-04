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


class TestSecretFromText(unittest.TestCase):
    def test_otpauth_url(self):
        uri = "otpauth://totp/Acme:alice?secret=JBSWY3DP&issuer=Acme"
        self.assertEqual(qr.secret_from_text(uri), "JBSWY3DP")

    def test_bare_base32(self):
        self.assertEqual(qr.secret_from_text("jbswy3dp"), "JBSWY3DP")

    def test_url_embedded_in_text(self):
        blob = "my token: otpauth://totp/x?secret=JBSWY3DP end"
        self.assertEqual(qr.secret_from_text(blob), "JBSWY3DP")

    def test_freeotp_json_byte_array(self):
        raw = b"Hello"
        expected = base64.b32encode(raw).decode().rstrip("=")
        js = '{"tokens":[{"type":"TOTP","secret":[72,101,108,108,111]}]}'
        self.assertEqual(qr.secret_from_text(js), expected)

    def test_freeotp_json_signed_bytes(self):
        # Java signed bytes: 200 unsigned is -56 signed.
        expected = base64.b32encode(bytes([200, 1, 255 & 0xFF])).decode().rstrip("=")
        js = '{"tokens":[{"type":"TOTP","secret":[-56, 1, -1]}]}'
        self.assertEqual(qr.secret_from_text(js), expected)

    def test_json_prefers_totp_over_hotp(self):
        totp = base64.b32encode(b"World").decode().rstrip("=")
        js = ('{"tokens":[{"type":"HOTP","secret":[1,2,3]},'
              '{"type":"TOTP","secret":[87,111,114,108,100]}]}')
        self.assertEqual(qr.secret_from_text(js), totp)

    def test_json_base32_string_secret(self):
        js = '{"secret":"JBSWY3DP"}'
        self.assertEqual(qr.secret_from_text(js), "JBSWY3DP")

    def test_empty(self):
        self.assertEqual(qr.secret_from_text("   "), "")
