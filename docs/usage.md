# Using it

## Connect / disconnect

- **Windows:** click **Connect** in the window, or use the tray icon. The status
  goes *Connecting…* → *Connected*; **Disconnect** shows *Disconnecting…* while it
  tears down.
- **Linux/macOS:** **left-click the tray icon** to toggle. Grey = disconnected,
  yellow (blinking) = connecting, green = connected, red = failed. Right-click for
  the menu (Connect / Disconnect / Setup / Autostart / Quit).

The login password and 2FA code are filled in automatically — you don't type
anything. (On the very first connect after a reboot the embedded login browser
may flash briefly; that's normal.)

## Status colours

| Colour | Meaning |
|--------|---------|
| ⚪ grey | disconnected |
| 🟡 yellow | connecting (auth + tunnel coming up) |
| 🟢 green | connected — traffic flows |
| 🔴 red | failed — click again to retry, or check the log |

On Windows the per-state colours are customisable in **Settings → Status
colours**.

## Closing the window (Windows)

While connected, closing the window asks what to do — **disconnect**, or keep the
tunnel **running in the background** (tray only). You can make that the default in
**Settings → Behaviour → On close**.

## Using a different VPN gateway

Nothing is tied to one organisation:

- **Windows:** open **Configuration** and set **Server** to your gateway and
  **Email** to your login.
- **Linux/macOS:** the tray **Setup** dialog has **Server** and **Group** fields.
- **Library:** set `server` / `user_email` in the config (below).

The built-in defaults just reflect what the tool was built and tested against
(Uni Graz).

## Headless library (CI / servers)

Wrap a block of code in a VPN session — same keyring-backed login, no GUI:

```python
from automatic_openconnect import auto_vpn_session, VPNError

config_data = {
    "auto_vpn": {
        "enabled": True,
        "user_email": "you@example.org",
        "server": "vpn.example.org",
    }
}

try:
    with auto_vpn_session(config_data):
        ...  # internal hosts are reachable inside this block
except VPNError as exc:
    print(f"VPN setup failed: {exc}")
```

When `auto_vpn.enabled` is not true, `auto_vpn_session` is a no-op that yields
`None`, so the same `with` block works whether or not the VPN is wanted. Store
the credentials once:

```bash
python -m automatic_openconnect.secrets set --email you@example.org
```
