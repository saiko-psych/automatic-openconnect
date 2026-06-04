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

import base64
import re
from urllib.parse import parse_qs, unquote, urlparse


class QRUnavailable(RuntimeError):
    """Raised when the optional QR-decoding dependency is missing."""


def extract_secret_from_otpauth(text: str) -> str:
    """Return the base32 TOTP secret encoded in a QR's text, or ''.

    Handles three shapes:
    - ``otpauth://totp/...?secret=BASE32`` (single account)
    - ``otpauth-migration://offline?data=...`` (Google Authenticator
      "export/transfer accounts" QR — base64 protobuf; the secret is raw
      bytes that we base32-encode)
    - a bare base32 string (some exports embed only the key)
    """
    text = (text or "").strip()
    low = text.lower()
    if low.startswith("otpauth-migration://"):
        return _extract_from_migration(text)
    if low.startswith("otpauth://"):   # totp or hotp setup QR
        secret = parse_qs(urlparse(text).query).get("secret", [""])[0]
        return _norm_base32(secret)
    bare = _norm_base32(text)
    if bare and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in bare):
        return bare
    return ""


def _norm_base32(s: str) -> str:
    """Normalise a base32 secret: drop spaces, uppercase, strip padding."""
    return (s or "").replace(" ", "").strip().upper().rstrip("=")


def secret_from_text(text: str) -> str:
    """Extract a base32 TOTP seed from pasted text. Accepts an
    ``otpauth://``/``otpauth-migration://`` URI, a FreeOTP/authenticator JSON
    export, an otpauth URI embedded in other text, or a bare base32 secret.
    """
    text = (text or "").strip()
    if not text:
        return ""
    low = text.lower()
    if low.startswith("otpauth://") or low.startswith("otpauth-migration://"):
        return extract_secret_from_otpauth(text)
    if text[0] in "[{":                      # looks like JSON (FreeOTP etc.)
        seed = _secret_from_json(text)
        if seed:
            return seed
    m = re.search(r"otpauth(?:-migration)?://[^\s\"']+", text, re.IGNORECASE)
    if m:                                    # URI pasted inside other text
        seed = extract_secret_from_otpauth(m.group(0))
        if seed:
            return seed
    return extract_secret_from_otpauth(text)  # bare-base32 fallback


def _secret_from_json(text: str) -> str:
    """Pull a TOTP seed out of an authenticator JSON export. FreeOTP+ stores
    the secret as a signed-byte array; others use a base32/base64 string."""
    import json
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return ""
    tokens: list = []
    if isinstance(data, dict):
        if isinstance(data.get("tokens"), list):
            tokens = data["tokens"]
        elif "secret" in data:
            tokens = [data]
        else:                                # tokens keyed by name
            tokens = [v for v in data.values() if isinstance(v, dict)]
    elif isinstance(data, list):
        tokens = data
    # Prefer a TOTP token (or one with no explicit type) over HOTP.
    def _is_totp(tok):
        return str(tok.get("type", "")).upper() in ("", "TOTP")
    ordered = ([t for t in tokens if isinstance(t, dict) and _is_totp(t)]
               + [t for t in tokens if isinstance(t, dict) and not _is_totp(t)])
    for tok in ordered:
        seed = _json_secret_to_base32(tok.get("secret"))
        if seed:
            return seed
    return ""


def _json_secret_to_base32(secret) -> str:
    if isinstance(secret, list) and secret:
        try:
            raw = bytes((int(x) & 0xFF) for x in secret)
        except (ValueError, TypeError):
            return ""
        return base64.b32encode(raw).decode("ascii").rstrip("=")
    if isinstance(secret, str):
        b32 = _norm_base32(secret)
        if b32 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in b32):
            return b32
        try:                                 # maybe base64-encoded raw bytes
            raw = base64.b64decode(secret + "=" * (-len(secret) % 4))
            if raw:
                return base64.b32encode(raw).decode("ascii").rstrip("=")
        except (ValueError, TypeError):
            pass
    return ""


# --- Google Authenticator otpauth-migration parsing ---------------------
# MigrationPayload { repeated OtpParameters otp_parameters = 1; ... }
# OtpParameters { bytes secret = 1; string name = 2; string issuer = 3;
#                 ... Type type = 6;  (2 == TOTP) }
# Parsed by hand (no protobuf dependency).

def _read_varint(buf: bytes, i: int):
    shift = val = 0
    while i < len(buf):
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not b & 0x80:
            return val, i
        shift += 7
    return val, i


def _iter_fields(buf: bytes):
    i, n = 0, len(buf)
    while i < n:
        tag, i = _read_varint(buf, i)
        field, wire = tag >> 3, tag & 7
        if wire == 0:
            val, i = _read_varint(buf, i)
            yield field, "varint", val
        elif wire == 2:
            ln, i = _read_varint(buf, i)
            yield field, "bytes", buf[i:i + ln]
            i += ln
        elif wire == 5:
            i += 4
        elif wire == 1:
            i += 8
        else:
            return


def _extract_from_migration(uri: str) -> str:
    # Search the whole URI (otpauth-migration has no netloc/path for
    # urlparse to split cleanly); grab the raw data= value.
    m = re.search(r"(?:[?&])data=([^&]*)", uri)
    if not m:
        return ""
    data = unquote(m.group(1))          # NOT parse_qs (it mangles '+')
    try:
        raw = base64.b64decode(data + "=" * (-len(data) % 4))
    except (ValueError, TypeError):
        return ""
    totp_secret = first_secret = b""
    for field, wire, val in _iter_fields(raw):
        if field == 1 and wire == "bytes":   # an OtpParameters message
            secret = b""
            otype = None
            for f2, w2, v2 in _iter_fields(val):
                if f2 == 1 and w2 == "bytes":
                    secret = v2
                elif f2 == 6 and w2 == "varint":
                    otype = v2
            if secret and not first_secret:
                first_secret = secret
            if secret and otype == 2 and not totp_secret:   # 2 == TOTP
                totp_secret = secret
    secret = totp_secret or first_secret
    if not secret:
        return ""
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def decode_qr_image(path: str) -> str:
    """Decode the first QR code in an image file; return its text ('' if
    none found). Raises QRUnavailable if OpenCV is not installed."""
    try:
        import cv2  # type: ignore
        import numpy as np
    except ImportError as exc:
        raise QRUnavailable("OpenCV (cv2) is required for QR detection.") from exc

    # Read via np.fromfile + imdecode: cv2.imread uses the ANSI file API and
    # silently returns None for paths with non-ASCII characters (umlauts,
    # synced folders). Reading the bytes ourselves avoids that.
    img = None
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        if buf.size:
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        img = None
    if img is None:
        img = cv2.imread(path)  # last resort
    if img is None:
        return ""

    detector = cv2.QRCodeDetector()

    def _try(im) -> str:
        # cv2's basic detector is finicky; try single then multi.
        text, _pts, _qr = detector.detectAndDecode(im)
        if text:
            return text
        ok, texts, _pts, _qr = detector.detectAndDecodeMulti(im)
        if ok and texts:
            for txt in texts:
                if txt:
                    return txt
        return ""

    # Try the image as-is, then grayscale, then a 2x upscale of each —
    # small/soft QR photos often only decode after scaling up.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    big_gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    for candidate in (img, gray, big, big_gray):
        text = _try(candidate)
        if text:
            return text
    return ""


def secret_from_qr_image(path: str) -> str:
    """Decode a QR image and return the embedded base32 TOTP seed ('' if
    none). Raises QRUnavailable if OpenCV is missing."""
    return extract_secret_from_otpauth(decode_qr_image(path))
