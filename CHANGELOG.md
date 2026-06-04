# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.2] - 2026-06-05

Fixes from clean-machine tester feedback.

### Fixed
- **`uv` not found** even after `pip install uv`: `uv` is now located on
  PATH, in `~/.local/bin` (official installer), and in a Python's Scripts dir
  (pip install) — wherever it actually landed.
- **openconnect.exe shown as missing** although installed: detection now also
  checks `Program Files (x86)` and `LOCALAPPDATA\Programs`; `openconnect-sso`
  is also found in `~/.local/bin` (where `uv tool` installs it, often off PATH).
- README/pyproject install command no longer uses bash `\` line-continuations
  (PowerShell rejected them) — it's a single line now.

### Added
- If `uv` is missing, the "Install now" button offers to **install uv
  automatically** (official installer, no admin / no Python), then continues
  with openconnect-sso.
- **Browse…** buttons in setup for the openconnect / openconnect-sso paths,
  so any install location works.
- Clearer prerequisite wording (OpenConnect-GUI only needs installing, not
  launching; how `openconnect-sso` / `uv` are handled).

## [0.1.1] - 2026-06-04

### Added
- **Global TOTP hotkey** (`Ctrl+Alt+P`): types the current 6-digit code into
  the focused field. Releases held modifiers first so German/AltGr layouts
  emit digits, not glyphs. Toggle in setup; seed pulled from the keyring.
- **App settings** view (separate from the VPN configuration): start at
  login (autostart), start minimised, tray notifications on/off; **light /
  dark theme** + six accent colours (accent also recolours the action
  icons); **user-pickable status colours** (connected / connecting /
  disconnected / error) for the dot and the tray icon; on-exit behaviour;
  open config/log folders; About & legal (MIT, third-party licences,
  "not affiliated with Uni Graz / uniIT").
- **In-app "Report a bug"** button → GitHub issue chooser, with bug-report /
  feature-request issue-form templates.
- **Wintun driver check** in the prerequisites checklist (advisory, never
  blocks): warns if `wintun.dll` isn't found near openconnect.
- Developer workflow: `python -m automatic_openconnect` entry point and a
  `dev.ps1` helper (editable-venv run/test, cache-busting reinstall).

### Changed
- The setup form is now the single place for configuration and shows the
  stored password + TOTP seed (masked, revealed by an in-field **eye icon**).
- Leaving the configuration no longer requires re-running setup: a **Back**
  button returns to the control view, and saving an existing setup no longer
  triggers a second admin prompt.
- The tray icon is rendered at runtime (coloured tile + padlock glyph) so any
  chosen status colour works, replacing the fixed coloured `.ico` files.

### Fixed
- Reconfiguring no longer wipes the `ui` block (language / close-on-exit).
- Checkbox indicators and combo-box arrows no longer clip (sub-controls are
  now fully styled instead of mixing stylesheet and native rendering).

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
