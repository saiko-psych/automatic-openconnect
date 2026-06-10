# automatic VPN

**Bring up a Cisco AnyConnect–compatible VPN automatically — without typing your
password or 2FA code every time.**

A **system-tray app** for **Windows, Linux and macOS** (one-click
connect/disconnect) plus a **headless Python library** for wrapping a block of
code in a VPN session. Your login password and optional TOTP 2-factor seed live
in the OS keyring — never in config or logs. It's a thin automation layer on top
of [openconnect-sso](https://github.com/vlaci/openconnect-sso), which speaks the
Cisco AnyConnect protocol.

[![tests](https://github.com/saiko-psych/automatic-openconnect/actions/workflows/tests.yml/badge.svg)](https://github.com/saiko-psych/automatic-openconnect/actions/workflows/tests.yml)
[![release](https://img.shields.io/github/v/release/saiko-psych/automatic-openconnect)](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/saiko-psych/automatic-openconnect/blob/main/LICENSE)

!!! tip "Works with **any** AnyConnect gateway"
    It was built for and is live-tested against the **University of Graz** VPN, so
    that gateway ships as the default — but nothing is hard-wired. Point the
    **server** at your own gateway and you're set.

## What you get

- **One click, no prompts.** Connect/disconnect from a tray icon; password and
  2FA are filled in automatically from the OS keyring.
- **Cross-platform, two shapes.** A full GUI on **Windows**; a lean tray on
  **Linux/macOS** (no elevation dance — `openconnect-sso` brings the tunnel up
  via passwordless `sudo`).
- **TOTP 2FA, opt-in.** Type the seed or import it from a **QR-code image**
  (incl. Google Authenticator export QRs). A global hotkey (`Ctrl+Alt+P`, Windows)
  types the current code into any focused field.
- **Headless library** for CI/servers, with the same keyring-backed login.

## Pick your platform

<div class="grid cards" markdown>

- :material-microsoft-windows: **Windows** — download the `.exe`, click through a
  guided setup. → [Install on Windows](installation/windows.md)
- :material-linux: **Linux** — lean tray; `pip install` from source or a prebuilt
  binary. → [Install on Linux](installation/linux.md)
- :material-apple: **macOS** *(experimental)* — the same lean tray.
  → [Install on macOS](installation/macos.md)

</div>

## How it works

```
tray / GUI
   └── openconnect-sso   SAML/Keycloak login in an embedded browser,
        │                auto-filled from the OS keyring
        └── openconnect   builds the Cisco AnyConnect tunnel
```

- **Windows** has no `sudo`, and the tunnel adapter (Wintun) needs Administrator,
  so a one-time **grant-once Scheduled Task** (a single UAC prompt) runs the
  backend elevated; connecting afterwards needs no elevation.
- **Linux/macOS** lean on `openconnect-sso` directly — it authenticates **and**
  launches `openconnect` via a passwordless `sudo` rule. No task, no elevation
  dance; the app is just a small tray.

!!! warning "Community tool"
    Provided as-is under the MIT licence, with no warranty and no affiliation
    with any VPN operator. See [Security](security.md) before storing a TOTP seed.
