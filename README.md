# automatic-openconnect

**Bring up a Cisco AnyConnect–compatible VPN automatically — without typing
your password or 2FA code every time.**

A small **Windows desktop app** (one‑click connect/disconnect from the system
tray) plus a **headless Python library** for wrapping a block of code in a VPN
session. Your login password and optional TOTP 2‑factor seed live in the OS
keyring, never in config or logs. Built as a thin automation layer on top of
[openconnect-sso], which speaks the Cisco AnyConnect protocol.

[![tests](https://github.com/saiko-psych/automatic-openconnect/actions/workflows/tests.yml/badge.svg)](https://github.com/saiko-psych/automatic-openconnect/actions/workflows/tests.yml)
&nbsp;[![release](https://img.shields.io/github/v/release/saiko-psych/automatic-openconnect)](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
&nbsp;[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> Works with **any** Cisco AnyConnect–compatible gateway that `openconnect-sso`
> can reach. It was originally built for and is live‑tested against the
> University of Graz VPN, so that gateway ships as the built‑in default — but
> nothing is hard‑wired to it. Point `server` at your own gateway and you're
> set ([see below](#using-a-different-vpn)).

## Highlights

- **One click, no prompts.** Connect/disconnect from a tray icon. A one‑time
  setup registers an elevated task (a single UAC prompt); connecting
  afterwards needs no elevation and pops no console windows.
- **No password / 2FA typing.** Credentials come from the OS keyring. The
  TOTP feature is opt‑in.
- **Global TOTP hotkey** (`Ctrl+Alt+P`): types the current 6‑digit code into
  whatever field has focus — handy for any 2FA prompt, not just the VPN.
- **Guided setup** with a live prerequisites check and one‑click fixes
  (create the login‑field template, install `openconnect-sso`, open the
  OpenConnect‑GUI download).
- **Customisable UI:** light/dark theme, accent colour, per‑state status
  colours, autostart at login, start‑minimised, tray notifications.
- **Crash‑safe:** a watchdog tears the tunnel down if the app dies; closing
  while connected asks whether to disconnect or keep it up in the background.
- **English / German**, switchable at runtime.
- **QR seed import** from an authenticator screenshot (incl. Google
  Authenticator export QR codes).
- **Headless library** for CI/servers, with the same keyring‑backed login.

## Install

### Desktop app (Windows)

**Easiest — download the executable:** grab `automatic-vpn.exe` from the
[latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
and run it. The build is unsigned, so SmartScreen shows *“Windows protected
your PC”* → **More info → Run anyway**.

**Or install with [uv]** (gets updates via `uv tool upgrade`). Run this as
**one line** — PowerShell does not accept the `\` line-continuations you may
know from bash:

```powershell
uv tool install --with PyQt6 --with "setuptools<70" --with opencv-python-headless --from git+https://github.com/saiko-psych/automatic-openconnect automatic-openconnect
```

Then run `automatic-vpn` (windowed) or `automatic-vpn-console` (keeps a
console open for tracebacks). `opencv-python-headless` is optional — it is
only needed to read a TOTP seed from a QR‑code image.

### Prerequisites

`openconnect-sso` and the `openconnect` engine are **not** bundled. The app's
first‑run checklist can install/locate them for you, or set them up manually:

| Component | Install |
| --- | --- |
| **openconnect-sso** (SAML/Keycloak login) | `uv tool install --with PyQt6 --with "setuptools<70" openconnect-sso` |
| **openconnect engine** | **Windows:** [OpenConnect‑GUI] (ships `openconnect.exe` **and** the Wintun driver) · **Linux:** `apt install openconnect` · **macOS:** `brew install openconnect` |

> The two `--with` pins are required by openconnect-sso 0.8.1: `setuptools<70`
> (it still imports `pkg_resources`) and `PyQt6` (its browser auth step).

## Desktop app — first run

The app walks you through the prerequisites, then collects your login email,
password and TOTP seed (stored in the Windows Credential Manager — you can
also import the seed from a QR‑code image). **Set up** registers a Scheduled
Task once (the single UAC prompt); after that, **Connect** needs no elevation.

App settings (theme, accent, status colours, autostart, notifications, the
TOTP hotkey toggle and legal/about info) live under the **Settings** button.

## Using a different VPN

Nothing is tied to any one organisation. In the desktop app, open
**Configuration** and set the **Server** to your own gateway and the **Email**
to your login. In the library, set `server` / `user_email` in the config (see
below). The bundled defaults simply reflect what the tool was built and tested
against.

## Library usage

```python
from automatic_openconnect import auto_vpn_session, VPNError

config_data = {
    "auto_vpn": {
        "enabled": True,
        "user_email": "you@example.org",   # your login email
        "server": "vpn.example.org",        # your Cisco AnyConnect gateway
    }
}

try:
    with auto_vpn_session(config_data):
        ...  # internal hosts are reachable inside this block
except VPNError as exc:
    print(f"VPN setup failed: {exc}")
```

When `auto_vpn.enabled` is not true, `auto_vpn_session` is a no‑op that yields
`None`, so the same `with` block works whether or not the VPN is wanted.

### Store your credentials

```sh
python -m automatic_openconnect.secrets set --email you@example.org
```

Prompts for your login password and TOTP base32 **seed** (the long string
behind “Cannot scan?” in an authenticator's setup screen — not the rotating
6‑digit code). They are written to the OS keyring under the `openconnect-sso`
service namespace. The desktop app stores the same secrets for you.

## Disclaimer

This is a **community tool**, provided as is under the MIT licence, with no
warranty and no affiliation with any VPN operator. Storing a TOTP seed in a
keyring is your decision and your responsibility: if you enable it, keep disk
encryption on (BitLocker / FileVault / LUKS) and a strong login password. The
TOTP feature is opt‑in.

<details>
<summary>Note for University of Graz members</summary>

Used against the official Uni Graz VPN, this tool is **not** an institutional
product and is **not supported by uniIT**. OpenConnect may be used “auf eigenes
Risiko und eigene Verantwortung” per the university policy
([Mitteilungsblatt 2007‑08/31.a](https://mitteilungsblatt.uni-graz.at/de/2007-08/31.a/pdf/)).
If you point the tool at a different organisation's VPN, follow that
organisation's own policy instead.

</details>

## License

MIT — see [LICENSE](LICENSE).

[openconnect-sso]: https://github.com/vlaci/openconnect-sso
[OpenConnect‑GUI]: https://github.com/openconnect/openconnect-gui/releases
[uv]: https://docs.astral.sh/uv/
