# Global TOTP hotkey

!!! success "Windows, Linux & macOS"
    Available on all three. Toggle it under **Settings** (Windows) or in the
    **tray menu → “TOTP-Hotkey (Ctrl+Alt+P)”** (Linux/macOS). See
    [Platform notes](#platform-notes) below — **macOS needs a one-time
    permission grant**, and Linux needs X11.

Press **`Ctrl+Alt+P`** anywhere and the app types your **current 6-digit TOTP
code** into whatever field has focus — handy for *any* 2FA prompt, not just the
VPN (webmail, a portal login, an SSH gateway…).

## How it works

- The code is generated on the fly from the TOTP **seed** in your keyring
  (the same seed the VPN login uses — see [Two-factor setup](authenticator-setup.md)).
- It's typed as synthetic keystrokes into the focused field, then you press Enter
  yourself.
- Nothing is shown on screen or copied to the clipboard.

## Requirements

- A TOTP seed must be stored (otherwise there's nothing to generate).
- The hotkey is enabled by default; toggle it in **Settings** (Windows) or the
  **tray menu** (Linux/macOS).

## Platform notes

=== "Windows"
    Works out of the box. Toggle under **Settings**.

=== "Linux"
    Toggle in the **tray menu → “TOTP-Hotkey (Ctrl+Alt+P)”**. It relies on
    `pynput`, which works on **X11**. On **Wayland** (the default on newer
    GNOME/KDE) the global key-grab and synthetic typing are blocked by the
    compositor, so the hotkey won't fire — log into an *X11/Xorg* session if you
    need it.

=== "macOS"
    Toggle in the **tray menu → “TOTP-Hotkey (Ctrl+Alt+P)”**. macOS gates global
    keyboard access behind **Privacy & Security**: the first time, grant the app
    (or the terminal you launched it from) both **Accessibility** *and* **Input
    Monitoring** in *System Settings → Privacy & Security*, then toggle the
    hotkey off and on again. Without the grant it's a **silent no-op** (the app
    keeps working; only the hotkey is inert).

!!! tip
    If `Ctrl+Alt+P` clashes with another app, disable it (Settings / tray menu).
    The code is only valid for ~30 seconds, so trigger it right before you need it.
