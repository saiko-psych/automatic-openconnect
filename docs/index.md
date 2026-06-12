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

## See it in action

<video controls muted playsinline preload="metadata" style="width:100%;max-width:780px;border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.18);">
  <source src="assets/vpn_demo.mp4" type="video/mp4">
  Your browser can't play the embedded video —
  <a href="assets/vpn_demo.mp4">download the demo (MP4)</a>.
</video>

*Guided setup → one-click connect → the uni webmail loads through the tunnel →
disconnect. Recorded in a clean Windows Sandbox.*

??? info "What happens in the video — step by step"
    1. **~0:00 — Get the app.** The GitHub release page; `automatic-vpn.exe` is
       downloaded.
    2. **~0:30 — First launch.** The app opens to the setup form — *Email*,
       *Server* (pre-filled with `univpn.uni-graz.at`), *Password*, *TOTP seed*,
       plus the options for the 2FA hotkey and for stopping conflicting VPNs.
    3. **~1:00 — Install the VPN engine.** The OpenConnect-GUI download page; it's
       installed (it ships `openconnect.exe` + the Wintun driver). Email and
       password are filled into the form.
    4. **~1:50 — Prerequisites all green → Set up.** Back in the app every
       prerequisite reads **[OK]** (“All set — you can connect”), and the
       **“Set up (one-time admin prompt)”** button is clicked — the single UAC.
    5. **~2:25 — Automatic login.** The uniLOGIN SSO browser opens and the
       **6-digit 2FA code is filled in for you** (no typing); the login completes.
    6. **~2:40 — Connecting → Connected.** The status goes from **“Connecting …”**
       to a green **“Connected”**.
    7. **~2:55 — Proof it's live.** The university webmail loads **through the
       tunnel**.

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
