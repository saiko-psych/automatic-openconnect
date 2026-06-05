# Security Policy

## Supported versions

Only the **latest release** is supported. Please reproduce issues on the
newest version from [Releases](https://github.com/saiko-psych/automatic-openconnect/releases/latest)
before reporting.

## How credentials are handled

- Your login **password** and (optional) **TOTP seed** are stored in the OS
  keyring (Windows Credential Manager) — **never** in the config file or logs.
- The rotating 6-digit code is generated locally; the **seed never leaves your
  machine** and nothing is uploaded anywhere.
- The TOTP feature is **opt-in**. If you enable it, keep full‑disk encryption
  on (BitLocker / FileVault / LUKS) and a strong login password.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

- Preferred: open a private **GitHub Security Advisory** via the repository's
  **Security → Report a vulnerability** tab.
- Alternatively, contact the maintainer (**@saiko-psych**) privately.

When reporting, include the version, OS, reproduction steps, and impact.
**Never paste a password or TOTP seed** — redact secrets from logs and
screenshots.

I'll acknowledge reports as soon as I can. This is a community project
maintained in spare time, so please allow reasonable time for a fix before any
public disclosure.

## Disclaimer

This is a community tool, provided **as is** under the MIT License with no
warranty, and is not affiliated with or supported by any VPN operator. Use is
at your own risk.
