# Install on Windows

A click-by-click walkthrough. No command line needed. Plan for ~10 minutes and
**two downloads**. If you prefer watching, the
[demo video](../index.md#see-it-in-action) shows the whole thing end to end.

!!! abstract "What gets installed, and why"
    | What | Why | Who installs it |
    |------|-----|-----------------|
    | **OpenConnect-GUI** | ships `openconnect.exe` (the VPN engine), the **Wintun** driver and the routing script | **you**, in Step 1 |
    | **automatic-vpn.exe** | this app — the friendly front-end that drives the engine | **you**, in Step 2 |
    | **openconnect-sso** | the login helper (handles the SSO/2FA browser login) | **the app**, one click in Step 3 |

---

## Step 1 — Install the VPN engine (OpenConnect-GUI)

1. Open **[gui.openconnect-vpn.net/download](https://gui.openconnect-vpn.net/download/)**.
2. Scroll to the **Windows** download and click the installer link (a file like
   `OpenConnect-GUI-Setup-x.x.x.exe`). Save it.
3. **Double-click** the downloaded installer to run it. If Windows asks *“Do you
   want to allow this app to make changes?”*, click **Yes** — the installer needs
   admin to place the Wintun driver.
4. Click **Next** on the welcome page, then **I Agree** on the licence page.
5. **The components page — the one step everyone misses.** You'll see a list of
   checkboxes. **Tick the “command-line / console version”** (sometimes labelled
   *“OpenConnect CLI”*).

    !!! danger "Don't skip this checkbox"
        That checkbox *is* the `openconnect.exe` this app drives. If you leave it
        unticked, only the graphical client is installed, `openconnect.exe` is
        missing, and later the app's prerequisites check will keep saying
        *“openconnect.exe not found”*. (You install it; you never open it.)

6. Leave the install folder at the default **`C:\Program Files\OpenConnect-GUI\`**
   and click **Install**.

    !!! tip "Why the default folder matters"
        The app auto-detects `openconnect.exe` in that standard location. A custom
        folder still works, but you'd have to point the app at it by hand later.

7. Wait for it to finish, then click **Finish**. **You never open OpenConnect-GUI
   yourself** — `automatic-vpn` launches the engine for you.

---

## Step 2 — Download the app

1. Open the **[latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest)**.
2. Under **“Assets”** (scroll down a little if needed), click **`automatic-vpn.exe`**
   to download it.
3. **Double-click** `automatic-vpn.exe` to run it.
4. Windows SmartScreen shows **“Windows protected your PC”**. Click **“More info”**,
   then the **“Run anyway”** button that appears.

    !!! note "Why the warning?"
        The `.exe` is unsigned (a free community tool — code signing costs money).
        The source is public on GitHub; nothing is hidden.

5. The app window opens.

---

## Step 3 — First run: the guided setup

Because nothing is configured yet, the app opens straight into the **setup form**.
Fill it top to bottom:

1. **Email** — your university email. This is your SSO username for the login.
2. **Server** — pre-filled with `univpn.uni-graz.at`. Leave it unless you're
   connecting to a different gateway.
3. **Password** — your login password.

    !!! info "Where your password goes"
        Into the **Windows Credential Manager** (the OS keyring) — **never** into a
        config file or a log. That's why you type it once here.

4. **TOTP seed** (2-factor) — three ways, pick one:
    - **type** the base32 seed string, or
    - click **“Load QR-code image…”** and select a screenshot/photo of your
      authenticator's QR code, or
    - click **“Paste URL / JSON…”** to paste an `otpauth://` link or a Google
      Authenticator export.

    Not sure where to get it? Click **“How do I get the seed?”** for a walkthrough
    (also in [Two-factor setup](../authenticator-setup.md)). *Why:* this lets the
    app generate your 6-digit code itself, so you never type a 2FA code again.

5. **Install the login helper.** If the app flags **openconnect-sso** as missing,
   click **“Install now”**. It installs it quietly with [uv] (and uv itself first
   if needed) — **no admin prompt, no Python knowledge**. Wait for it to report
   done.
6. **openconnect.exe** from Step 1 is detected automatically. If for some reason
   it isn't, click **“Locate openconnect.exe…”** and browse to
   `C:\Program Files\OpenConnect-GUI\openconnect.exe`.
7. Click **“Set up (one-time admin prompt)”**. A **UAC prompt** appears — click
   **Yes**.

    !!! info "What that one admin prompt does"
        The tunnel adapter (Wintun) needs Administrator rights. Rather than ask
        every time, the app registers a **Scheduled Task once** under this single
        UAC prompt. From now on **Connect needs no admin prompt and opens no
        console window**. You approve admin *exactly once* — right here.

8. You'll see **“Done”**. The window switches to the main control screen.

---

## Step 4 — Connect

1. Click **“Connect”**. The status moves through **“Signing in …”** → green
   **“Connected”**. A login browser may flash up briefly — it fills itself in from
   your keyring and closes on its own.

    !!! note "If it takes a moment"
        A slow login browser can make it sit on *“Signing in …”* for a bit — that's
        normal. The app waits for the real result; it won't falsely say “failed”.

2. Open **`webmail.uni-graz.at`** (or any internal page) to confirm you're going
   through the tunnel.
3. Click **“Disconnect”** when you're done.

---

## After setup — useful buttons

- **“Configuration…”** — reopen the setup form to change email/server/password/2FA
  (then **“Save changes”**).
- **“Check prerequisites”** — re-runs the engine/login checks and offers fix
  buttons (the same **“Install now”** / **“Locate openconnect.exe…”** helpers).
- **“Show log”** — the connect log, for troubleshooting / **“Report a bug”**.

!!! info "Autostart at login"
    **Settings → Start & tray → Autostart** registers the app under the
    `HKCU…\Run` key, so it launches into the tray every time you log in.

!!! tip "Type your 2FA code anywhere"
    With a TOTP seed stored, **`Ctrl+Alt+P`** types your current 6-digit code into
    whatever field has focus — handy for webmail or any 2FA prompt, not just the
    VPN. See [the TOTP hotkey](../totp-hotkey.md). *(Windows only.)*

??? note "Advanced — install without the .exe (via uv)"
    ```powershell
    uv tool install --with PyQt6 --with "setuptools<70" --with opencv-python-headless --from git+https://github.com/saiko-psych/automatic-openconnect automatic-openconnect
    ```
    Then run `automatic-vpn`.

[uv]: https://docs.astral.sh/uv/
