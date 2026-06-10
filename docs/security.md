# Security

## Where secrets live

Your **login password** and optional **TOTP seed** are stored in the **OS
keyring**, never in config files or logs:

| OS | Backend |
|----|---------|
| Windows | Credential Manager |
| Linux | KWallet / GNOME-Keyring (libsecret) |
| macOS | Keychain |

They're stored under the `openconnect-sso` namespace (password under your email,
seed under `totp/<email>`) so the login helper can read them directly. Config
(`config.json`) holds only non-secret settings (email, server, paths).

## The TOTP trade-off

Storing a TOTP **seed** means the app can generate your 2FA code — which also
means anyone with access to your unlocked session + keyring could too. The
feature is **opt-in**. If you enable it:

- keep **disk encryption** on (BitLocker / FileVault / LUKS), and
- use a **strong login password** (the keyring is only as safe as your session).

If that trade-off isn't for you, leave TOTP off and type the 6-digit code
yourself — everything else still works.

## Elevation / privileges

- **Windows:** the tunnel adapter (Wintun) needs Administrator. A one-time
  **grant-once Scheduled Task** (single UAC) runs the backend elevated;
  day-to-day connecting needs no elevation. The task runs only the app's
  `up`/`down` backend.
- **Linux/macOS:** a **passwordless-sudo rule scoped to `openconnect`** lets the
  tray bring the tunnel up without a password prompt. The rule is limited to
  `/usr/bin/openconnect` (+ `killall openconnect`) — not blanket sudo.

## Network trust

The app shells out to `openconnect-sso` / `openconnect`; it does not implement
its own crypto or SAML. It pins the server certificate fingerprint that
`openconnect-sso` returns for the connection.

## Disclaimer

This is a **community tool**, provided as-is under the MIT licence, with **no
warranty** and **no affiliation** with any VPN operator.

??? note "Note for University of Graz members"
    Used against the official Uni Graz VPN, this tool is **not** an institutional
    product and is **not supported by uniIT**. OpenConnect may be used “auf
    eigenes Risiko und eigene Verantwortung” per
    [Mitteilungsblatt 2007-08/31.a](https://mitteilungsblatt.uni-graz.at/de/2007-08/31.a/pdf/).
    Pointing the tool at another organisation's VPN means following that
    organisation's policy instead.
