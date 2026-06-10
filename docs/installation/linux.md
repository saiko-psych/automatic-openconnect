# Install on Linux

On Linux `openconnect-sso` does the whole job — it runs the SAML auth **and**
launches `openconnect` via passwordless `sudo`. So there's no scheduled-task /
elevation dance: the app is just a small **system-tray**.

!!! success "Tested on EndeavourOS (Arch). Should work on any modern desktop Linux."

## 1. Prerequisites

Install the two engines and set a passwordless-sudo rule so the tray can bring
the tunnel up/down:

=== "Arch / EndeavourOS"
    ```bash
    sudo pacman -S openconnect
    # openconnect-sso via uv (recommended):
    uv tool install openconnect-sso
    ```

=== "Debian / Ubuntu"
    ```bash
    sudo apt install openconnect
    uv tool install openconnect-sso
    ```

Then the sudoers rule (so `sudo openconnect` / `sudo killall openconnect` run
without a password prompt):

```bash
sudo visudo -f /etc/sudoers.d/openconnect
```
```
<your-user> ALL=(ALL) NOPASSWD: /usr/bin/openconnect, /usr/bin/killall openconnect
```

## 2. Install the app

=== "From source (recommended)"
    ```bash
    git clone https://github.com/saiko-psych/automatic-openconnect.git
    cd automatic-openconnect
    uv venv && source .venv/bin/activate
    uv pip install -e ".[qr]"   # PyQt6 is pulled in automatically; [qr] adds QR-image import
    ```

=== "Prebuilt binary"
    Download `automatic-vpn-linux-x86_64` from the
    [latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest):
    ```bash
    chmod +x automatic-vpn-linux-x86_64
    ./automatic-vpn-linux-x86_64
    ```
    !!! note
        The binary is built on a recent glibc and is unsigned. If it won't start,
        use the source install (the verified path).

## 3. First run

Start it **detached**, so your terminal stays free:

```bash
setsid python -m automatic_openconnect </dev/null &>/dev/null &
```

A tray icon appears. On first run the **setup dialog** opens — enter your email,
server, auth group, and (if not already in your keyring) password + TOTP
(typed or imported from a QR-code image → [details](../authenticator-setup.md)).
Click the icon to connect/disconnect.

## 4. Autostart at login

Tray menu → **“Autostart beim Login”**. After the next login the tray starts on
its own — no terminal needed. It writes
`~/.config/autostart/automatic-openconnect.desktop`.

!!! warning "Using an older standalone tray?"
    If you previously ran a hand-rolled tray, remove its autostart so you don't
    get two icons: `rm ~/.config/autostart/vpn-tray.desktop`
