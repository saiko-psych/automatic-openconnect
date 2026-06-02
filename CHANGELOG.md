# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.0.1] - 2026-06-02

### Added
- Initial extraction from the Termino project (Phase 1 of the roadmap).
- `automatic_openconnect` package:
  - `auto_vpn_session` cross-platform factory (Linux + Windows backends;
    no-op on macOS/unknown until the Phase 2 port lands).
  - `_linux.py` - openconnect-sso + xvfb-run headless tunnel.
  - `_windows.py` - openconnect.exe path, no sudo, service de-confliction.
  - `core.py` - shared `VPNError`.
  - `secrets.py` - keyring access for the `openconnect-sso` namespace
    (login password + TOTP seed), with a small management CLI.
- Tests for both backends (mocked, run green on Linux CI).

### Notes
- Use at your own risk. Not supported by uniIT. See README.
- macOS port, setup wizards, TOTP hotkey daemon, and docs come in later
  phases.
