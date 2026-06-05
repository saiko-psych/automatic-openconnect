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

## Setup (Windows)

Three steps. The app does the heavy lifting — you don't need the command line.

### 1. Install the VPN engine (OpenConnect-GUI)

Download and run the **official installer**:
**https://gui.openconnect-vpn.net/download/**

> [!IMPORTANT]
> In the installer, make sure the **command-line / console version**
> component is **ticked** — that's the CLI `openconnect.exe` the app drives.
> Without it the GUI is installed but `openconnect.exe` is missing.

> Use the **installer**, not a single `openconnect.exe` you found somewhere — a
> loose exe does **not** work. It needs its DLLs, the routing script and the
> Wintun driver, which the installer puts in place together (in
> `C:\Program Files\OpenConnect-GUI\`). You only install it; you never open it.

### 2. Get the app

Download **`automatic-vpn.exe`** from the
[latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
and run it. It's unsigned, so SmartScreen shows *“Windows protected your PC”* →
**More info → Run anyway**.

### 3. First run — the guided setup

The app checks the prerequisites and fixes what it can:

- **openconnect-sso** (the SAML/Keycloak login helper): click **Install now**.
  The app installs it with [uv] — and installs uv itself first if you don't
  have it. No admin rights, no Python needed.
- It auto-detects `openconnect.exe` from step 1. (If you point at it manually,
  pick **`openconnect.exe`**, not `openconnect-gui.exe` — the app corrects that
  for you anyway.)
- Enter your **email**, **password** and **TOTP seed**. You can type the seed,
  **load a QR-code image**, or **paste an `otpauth://` URL or a JSON export**
  (e.g. from FreeOTP). Secrets go into the Windows Credential Manager — never
  into config or logs.
- Click **Set up**. That registers a scheduled task once (a single UAC
  prompt). Afterwards **Connect** needs no elevation and opens no console.

Done — one click (or the tray icon) connects, with password and 2FA filled
automatically. Theme, accent, per-state colours, autostart, notifications, the
`Ctrl+Alt+P` TOTP hotkey and legal/about info live behind the **Settings**
button.

> **Advanced (no .exe):** install everything via [uv] instead — one line
> (PowerShell rejects bash `\` continuations):
> ```powershell
> uv tool install --with PyQt6 --with "setuptools<70" --with opencv-python-headless --from git+https://github.com/saiko-psych/automatic-openconnect automatic-openconnect
> ```
> then run `automatic-vpn`. On **Linux/macOS** (library use) install the
> engine with `apt install openconnect` / `brew install openconnect` and
> `openconnect-sso` via uv.

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
