# Global TOTP hotkey

!!! note "Windows only"
    The global hotkey lives in the Windows app. (The Linux/macOS tray doesn't
    register one.)

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
- The hotkey is enabled by default; toggle it in **Settings**.

!!! tip
    If `Ctrl+Alt+P` clashes with another app, it can be disabled in Settings.
    The code is only valid for ~30 seconds, so trigger it right before you need it.
