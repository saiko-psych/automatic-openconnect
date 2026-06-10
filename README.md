# automatic-openconnect

**Bring up a Cisco AnyConnect–compatible VPN automatically — without typing
your password or 2FA code every time.**

A **system-tray app** for **Windows, Linux & macOS** (one-click
connect/disconnect) plus a **headless Python library**. Your login password and
optional TOTP 2-factor seed live in the OS keyring — never in config or logs.
A thin automation layer over [openconnect-sso].

[![tests](https://github.com/saiko-psych/automatic-openconnect/actions/workflows/tests.yml/badge.svg)](https://github.com/saiko-psych/automatic-openconnect/actions/workflows/tests.yml)
&nbsp;[![docs](https://readthedocs.org/projects/automatic-openconnect/badge/?version=latest)](https://automatic-openconnect.readthedocs.io/en/latest/)
&nbsp;[![release](https://img.shields.io/github/v/release/saiko-psych/automatic-openconnect)](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
&nbsp;[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## 📖 Documentation

**Everything — install, usage, 2FA, troubleshooting, internals — lives here:**

### → [automatic-openconnect.readthedocs.io](https://automatic-openconnect.readthedocs.io/)

Install [Windows](https://automatic-openconnect.readthedocs.io/en/latest/installation/windows/)
· [Linux](https://automatic-openconnect.readthedocs.io/en/latest/installation/linux/)
· [macOS](https://automatic-openconnect.readthedocs.io/en/latest/installation/macos/)
&nbsp;|&nbsp;
[Using it](https://automatic-openconnect.readthedocs.io/en/latest/usage/)
· [Two-factor](https://automatic-openconnect.readthedocs.io/en/latest/authenticator-setup/)
· [Security](https://automatic-openconnect.readthedocs.io/en/latest/security/)
· [Troubleshooting](https://automatic-openconnect.readthedocs.io/en/latest/troubleshooting/)
· [For developers](https://automatic-openconnect.readthedocs.io/en/latest/developer/)

## Get it

- **Windows** — download `automatic-vpn.exe` from the
  [latest release](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
  and follow the guided setup.
- **Linux / macOS** — a lean tray; prebuilt binary or `pip install` from source
  (*macOS experimental*).

> Works with **any** AnyConnect gateway `openconnect-sso` can reach. Built for
> and live-tested against the University of Graz VPN (the default), but nothing
> is hard-wired — point the server at your own gateway.

## License & disclaimer

**MIT** — see [LICENSE](LICENSE). A community tool: **no warranty, no
affiliation** with any VPN operator. The TOTP feature is opt-in. Full notes →
[Security](https://automatic-openconnect.readthedocs.io/en/latest/security/).

[openconnect-sso]: https://github.com/vlaci/openconnect-sso
