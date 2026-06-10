# Troubleshooting

## Windows

??? failure "Prerequisites check says “openconnect not found”"
    You installed OpenConnect-GUI but **didn't tick the “command-line / console
    version”** component → there's no `openconnect.exe`. Re-run the installer and
    enable it. See [Install on Windows](installation/windows.md).

??? failure "SmartScreen: “Windows protected your PC”"
    The `.exe` is unsigned. **More info → Run anyway.**

??? failure "Connect shows “connected” but you have no internet / can't reach internal sites"
    Fixed in **v0.1.24**. The cause was openconnect being launched without a
    console, so its route-configuration script (`vpnc-script-win.js`, run via
    `cscript`) hung and the tunnel came up without routes. Make sure you're on the
    [latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
    (Configuration → **Save** once after updating, then Connect).

??? failure "A connection has to be set up while on battery / nothing happens after Connect"
    Fixed in **v0.1.16** — the Scheduled Task now allows running on battery. Update,
    then **Configuration → Save** once to re-register the task.

??? failure "It connects but takes very long / needs two clicks to disconnect"
    Fixed in **v0.1.25/0.1.26** (the auto-reconnect loop was removed and the
    teardown moved off the UI thread). Update to the latest release.

!!! tip "See what happened"
    **Settings → Maintenance → Open log** (or the **Show log** link on a failed
    connect) shows the full connect log. **Report issues** with that log attached.

## Linux

??? failure "Two tray icons after login"
    An older standalone tray is still autostarting. Remove its entry:
    `rm ~/.config/autostart/vpn-tray.desktop` and `pkill -f vpn-tray.py`.

??? failure "`ModuleNotFoundError: No module named 'PyQt6'`"
    Reinstall so the dependency is pulled: `uv pip install -e .` (PyQt6 is a
    dependency on Linux/macOS) — or `uv pip install PyQt6`.

??? failure "Running it blocks the terminal"
    That's normal for a foreground GUI. Start it **detached**
    (`setsid python -m automatic_openconnect </dev/null &>/dev/null &`) or enable
    **Autostart** in the tray menu so the desktop launches it at login.

??? failure "Disconnect asks for a sudo password / fails"
    The passwordless-sudo rule is missing or wrong. See the sudoers step in
    [Install on Linux](installation/linux.md).

??? failure "Prebuilt binary won't start"
    PyInstaller+Qt on Linux can hit platform-plugin issues. Use the **source
    install** (`uv pip install -e .`) — it's the verified path.

## Both / general

??? failure "2FA step is rejected"
    The stored TOTP **seed** is wrong (you may have saved the 6-digit code instead
    of the long Base32 seed). Re-import it — see
    [Two-factor setup](authenticator-setup.md). Verify with
    `oathtool --totp -b <SEED>`.

??? failure "Login window opens but doesn't auto-fill"
    The credentials aren't in the keyring under the **exact** email you connect
    with. Re-enter them in the setup dialog (or
    `python -m automatic_openconnect.secrets set --email <you>`).

??? question "The login page changed and auto-fill broke"
    The Keycloak field selectors live in `~/.config/openconnect-sso/config.toml`.
    They may need updating if your IdP's login page changes.
