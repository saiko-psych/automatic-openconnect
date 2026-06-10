# Two-factor (TOTP) — set up the seed

The TOTP feature is **opt-in**. When enabled, the app fills your 6-digit 2FA code
automatically. To do that it needs the **TOTP seed** (the long Base32 string
behind *“Can't scan the QR code?”* in an authenticator's setup screen — **not** the
rotating 6-digit code).

!!! info "Where the seed is stored"
    Under the `openconnect-sso` keyring namespace: the password under your email,
    the seed under `totp/<email>`. On Windows that's the Credential Manager; on
    Linux KWallet/GNOME-Keyring; on macOS the Keychain. Never in config or logs.

## Ways to import the seed

=== "Type it"
    Paste the Base32 string (e.g. `JBSWY3DPEHPK3PXP`) into the **TOTP** field of
    the setup dialog.

=== "QR-code image"
    Click **QR-Bild…** (Linux/macOS) or **load a QR-code image** (Windows) and
    pick a screenshot/photo of the QR. The app decodes:

    - a normal `otpauth://totp/…?secret=…` QR, and
    - a **Google Authenticator export** QR (`otpauth-migration://…`, first account).

    !!! note "Linux/macOS needs the `qr` extra"
        Install with `uv pip install -e ".[qr]"` (adds opencv for QR decoding).

=== "otpauth:// URL (Windows)"
    Paste an `otpauth://` URL or a JSON export directly into the setup.

## Get the seed from your authenticator

- **New TOTP at the provider:** during setup most sites show the secret in plain
  text under “Can't scan?” — copy that.
- **Existing Google Authenticator:** menu → *Transfer accounts → Export* shows a
  migration QR; screenshot it and use the QR-image import.

!!! tip "Verify it works"
    After saving, connect once. If the 2FA step is rejected, the seed is wrong —
    re-import it. A quick check on the CLI: `oathtool --totp -b <SEED>` should
    match your authenticator's current code.
