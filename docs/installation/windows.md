# Install on Windows

Three steps. The app does the heavy lifting — you don't need the command line.

## 1. Install the VPN engine (OpenConnect-GUI)

Download and run the **official installer**:
**[gui.openconnect-vpn.net/download](https://gui.openconnect-vpn.net/download/)**

!!! danger "The one step everyone misses"
    On the installer's components page, **tick the “command-line / console
    version”** before clicking Install. That component *is* the CLI
    `openconnect.exe` this app drives. Without it, only the graphical client is
    installed, `openconnect.exe` is missing, and the prerequisites check keeps
    saying openconnect is not found. (You install it; you never open it.)

Use the **installer**, not a loose `openconnect.exe` — it needs its DLLs, the
routing script and the **Wintun** driver, which the installer places together in
`C:\Program Files\OpenConnect-GUI\`.

## 2. Get the app

Download **`automatic-vpn.exe`** from the
[latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
and run it.

!!! note "SmartScreen"
    The `.exe` is unsigned, so SmartScreen shows *“Windows protected your PC”* →
    **More info → Run anyway**.

## 3. First run — the guided setup

The app checks prerequisites and fixes what it can:

- **openconnect-sso** (the SAML/Keycloak login helper): click **Install now** —
  it's installed with [uv] (and uv itself first if missing). No admin, no Python.
- It auto-detects `openconnect.exe` from step 1.
- Enter your **email**, **password** and **TOTP seed** (type it, load a QR-code
  image, or paste an `otpauth://` URL). Secrets go into the Windows Credential
  Manager — never into config or logs. → [Two-factor setup](../authenticator-setup.md)
- Click **Set up**. This registers a Scheduled Task once (a single **UAC
  prompt**). Afterwards **Connect** needs no elevation and opens no console.

Done — one click (or the tray icon) connects, with password and 2FA filled
automatically. Theme, accent, autostart, notifications, the `Ctrl+Alt+P`
[TOTP hotkey](../totp-hotkey.md) and more live behind **Settings**.

!!! info "Autostart at login"
    **Settings → Start & tray → Autostart** registers the app under the
    `HKCU…\Run` key so it launches into the tray at login.

??? note "Advanced — install without the .exe (via uv)"
    ```powershell
    uv tool install --with PyQt6 --with "setuptools<70" --with opencv-python-headless --from git+https://github.com/saiko-psych/automatic-openconnect automatic-openconnect
    ```
    Then run `automatic-vpn`.

[uv]: https://docs.astral.sh/uv/
