# src/automatic_openconnect/qr.py
# -*- coding: utf-8 -*-
"""Extract a TOTP seed from a QR-code image.

Authenticator QR codes encode an ``otpauth://totp/<label>?secret=<BASE32>&...``
URI. This module decodes the QR (via OpenCV, an optional dependency) and
pulls the base32 ``secret`` out of that URI.

The URI parsing (:func:`extract_secret_from_otpauth`) is pure and unit-
tested; the image decoding (:func:`decode_qr_image`) needs ``cv2`` and is
guarded so the rest of the app works without it.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse


class QRUnavailable(RuntimeError):
    """Raised when the optional QR-decoding dependency is missing."""


def extract_secret_from_otpauth(text: str) -> str:
    """Return the base32 secret from an otpauth:// URI, else ''.

    Tolerates a bare base32 secret too (some exports embed only the key).
    """
    text = (text or "").strip()
    if text.lower().startswith("otpauth://"):
        secret = parse_qs(urlparse(text).query).get("secret", [""])[0]
        return secret.strip()
    # A bare base32 string (A-Z, 2-7, optional padding) — accept as-is.
    bare = text.replace(" ", "").upper()
    if bare and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in bare):
        return bare
    return ""


def decode_qr_image(path: str) -> str:
    """Decode the first QR code in an image file; return its text ('' if
    none found). Raises QRUnavailable if OpenCV is not installed."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise QRUnavailable(
            "QR-Erkennung benötigt OpenCV. Installation:\n"
            "  uv tool install --reinstall --with opencv-python-headless "
            "--with PyQt6 --with \"setuptools<70\" automatic-openconnect"
        ) from exc
    img = cv2.imread(path)
    if img is None:
        return ""
    data, _points, _qr = cv2.QRCodeDetector().detectAndDecode(img)
    return data or ""


def secret_from_qr_image(path: str) -> str:
    """Decode a QR image and return the embedded base32 TOTP seed ('' if
    none). Raises QRUnavailable if OpenCV is missing."""
    return extract_secret_from_otpauth(decode_qr_image(path))
