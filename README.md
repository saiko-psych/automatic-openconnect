# automatic-openconnect

**Connect to the University of Graz VPN (`univpn.uni-graz.at`) automatically,
without typing your password or 2FA code every time.**

This tool brings the Uni Graz VPN tunnel up around a block of your code and
tears it down again afterwards, pulling your login password and (optionally)
your TOTP 2-factor code from the OS keyring. It was built for — and is
live-verified against — the Uni Graz VPN. It is headless and cross-platform
(Linux, Windows, macOS planned).

It is a thin automation layer on top of [openconnect-sso], which speaks the
Cisco AnyConnect protocol.

### Works with other VPNs too

Nothing here is hard-wired to Uni Graz. Any Cisco AnyConnect–compatible VPN
that `openconnect-sso` can reach works the same way — just point `server` at
your own gateway and use your own login email (see [Usage](#usage-library)).
The Uni Graz defaults and the notes below are simply there because that is
what it was built and tested for.

> ## ⚠️ For University of Graz members: use at your own risk — not supported by uniIT
>
> The note in this box applies specifically to **members of the University of
> Graz** using this tool against the official Uni Graz VPN. (If you point it
> at a different organisation's VPN, follow that organisation's own policy
> instead.)
>
> This is a **community tool**, hosted on a personal account. It is **not** an
> institutional product and is **not supported by uniIT** (the Uni Graz IT
> department) or any other IT department. At Uni Graz, OpenConnect may be used
> "auf eigenes Risiko und eigene Verantwortung" per the university policy
> ([Mitteilungsblatt 2007-08/31.a](https://mitteilungsblatt.uni-graz.at/de/2007-08/31.a/pdf/)).
> Storing your TOTP seed in a keyring is your decision and your
> responsibility. If you enable it, keep disk encryption on (BitLocker /
> FileVault / LUKS) and a strong login password. The TOTP feature is
> **opt-in**.

## Status

Early. **Phase 1** (code extraction from the Termino project) is done:
the Linux and Windows backends, the keyring helper, and their test suites
are in place. macOS port, setup wizards, the Ctrl+Alt+P TOTP hotkey
daemon, and the Read the Docs site come in later phases.

## Install

No PyPI release yet — install straight from git:

```
uv tool install --with PyQt6 --with "setuptools<70" \
    --from git+https://github.com/saiko-psych/automatic-openconnect \
    automatic-openconnect
```

`openconnect-sso` itself is installed separately (it is not bundled). The
two `--with` pins are required by openconnect-sso 0.8.1:
`setuptools<70` because it still imports `pkg_resources`, and `PyQt6` for
its headless browser auth step.

You also need the `openconnect` CLI on PATH:

- Linux: `apt install openconnect` (or your distro's package)
- Windows: the `openconnect-gui` bundle (ships `openconnect.exe`)
- macOS: `brew install openconnect`

## Usage (library)

```python
from automatic_openconnect import auto_vpn_session, VPNError

config_data = {
    "auto_vpn": {
        "enabled": True,
        "user_email": "you@example.uni-graz.at",  # your login email
        "server": "univpn.uni-graz.at",            # Uni Graz default; swap for another gateway
    }
}

try:
    with auto_vpn_session(config_data):
        ...  # internal hosts reachable inside this block
except VPNError as exc:
    print(f"VPN setup failed: {exc}")
```

When `auto_vpn.enabled` is not true, `auto_vpn_session` is a no-op that
yields `None`, so the same `with` block works whether or not the VPN is
wanted.

## Store your credentials

```
python -m automatic_openconnect.secrets set --email you@example.uni-graz.at
```

Prompts for your login password and TOTP base32 **seed** (the long
string behind "Cannot scan?" in the authenticator setup — not the
rotating 6-digit code). They are written to the OS keyring under the
`openconnect-sso` service namespace.

## License

MIT. See [LICENSE](LICENSE).

[openconnect-sso]: https://github.com/vlaci/openconnect-sso
