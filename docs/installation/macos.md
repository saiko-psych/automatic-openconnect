# Install on macOS

!!! warning "Experimental"
    The macOS tray is **written but not yet verified on a real Mac**. The code
    paths (utun detection, LaunchAgent autostart, `sudo killall openconnect`)
    are in place and the binary builds in CI, but it hasn't had a live test. If
    you try it, [feedback](https://github.com/saiko-psych/automatic-openconnect/issues)
    is very welcome.

macOS works the same way as Linux: `openconnect-sso` does the SAML auth **and**
launches `openconnect` via passwordless `sudo`, and the app is a lean tray.

## 1. Prerequisites

```bash
brew install openconnect
uv tool install openconnect-sso
```

Passwordless sudo for `openconnect` (so the tray can bring the tunnel up):

```bash
sudo visudo -f /etc/sudoers.d/openconnect
```
```
<your-user> ALL=(ALL) NOPASSWD: /opt/homebrew/bin/openconnect, /usr/bin/killall openconnect
```
(Use the path from `which openconnect` — `/usr/local/bin/openconnect` on Intel Macs.)

## 2. Install the app

=== "From source (recommended)"
    ```bash
    git clone https://github.com/saiko-psych/automatic-openconnect.git
    cd automatic-openconnect
    uv venv && source .venv/bin/activate
    uv pip install -e ".[gui,qr]"   # [gui] = PyQt6 + the tray; [qr] adds QR-image import
    ```

=== "Prebuilt binary"
    Download `automatic-vpn-macos` from the
    [latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest).
    It's **unsigned**, so Gatekeeper will block it on first launch:
    right-click → **Open** → **Open**, or
    `xattr -d com.apple.quarantine automatic-vpn-macos`.

## 3. First run

```bash
python -m automatic_openconnect
```

The setup dialog opens (email / server / group + password / TOTP →
[details](../authenticator-setup.md)). The tray icon connects/disconnects.

## 4. Autostart

Tray menu → **“Autostart beim Login”** writes a LaunchAgent
(`~/Library/LaunchAgents/at.uni-graz.automatic-openconnect.plist`) that starts
the tray at login.
