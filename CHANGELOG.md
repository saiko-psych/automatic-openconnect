# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-06-04

### Added
- **Windows desktop app** (`automatic-vpn` / `automatic-vpn-console`,
  `automatic_openconnect.gui`):
  - One-click connect/disconnect with live status and coarse progress
    steps (preparing → signing in → bringing tunnel up → connected).
  - **Grant-once elevation**: a one-time UAC registers a Scheduled Task;
    connecting afterwards needs no elevation and pops no console window
    (windowless `pythonw.exe` + `CREATE_NO_WINDOW` on every helper).
  - **System tray** icon with state colour (green/amber/blue/red),
    left-click toggle, close-to-tray, and quit-with-teardown.
  - **Crash-safe teardown**: a GUI heartbeat watchdog tears the tunnel
    down if the GUI dies; close-while-connected asks disconnect vs keep in
    background (remembered).
  - **Guided setup** with one-click fixes: create `config.toml`, install
    `openconnect-sso` via uv, open the openconnect-gui download page;
    prerequisites are re-checked automatically before each connect.
  - **TOTP help** and **QR-image seed import** (optional `qr` extra,
    OpenCV).
  - **English/German** UI, switchable in-app (English default).
- `config.py` (per-machine config in `%PROGRAMDATA%`), `gui_logic.py`,
  `preflight.py`, `qr.py`, `session.py`, `i18n.py`, `tasks_windows.py`.
- `--config` accepted after the `up`/`down`/`status` subcommand.

### Changed
- Config is stored in `%PROGRAMDATA%\automatic-openconnect\config.json`
  (not `%APPDATA%`) so the elevated Scheduled Task can read it.

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
