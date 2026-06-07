# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.12] - 2026-06-07

### Changed
- **One-shot connect diagnostics.** When Connect times out with no backend
  output, the log now records everything needed to pinpoint the cause in a
  single run: the Scheduled Task's actual action (exe + arguments), whether
  that exe exists and matches the running app, a `last-connect.error`
  breadcrumb, and — decisively — the output of running the same exe with a new
  hidden `diag` subcommand directly (no connect). This distinguishes "the exe
  can't run in CLI mode" from "the elevated task launch is being blocked"
  (e.g. antivirus/device policy on the unsigned exe).

## [0.1.11] - 2026-06-07

### Fixed
- **Connect that "does nothing" then times out is now diagnosable.** The
  connection log is never empty: the app writes a preamble *before* firing the
  elevated task and records the Scheduled Task's last-run result, so a failed
  connect explains *why* instead of showing "No connection log yet." (Targets
  the tester reports where Connect timed out with no log output.)
- **"Services to stop" now keeps an emptied list.** Clearing the field and
  saving previously reverted to the defaults (an empty list was treated as
  "unset"); an explicitly-empty list is now respected on save and reload.

## [0.1.10] - 2026-06-07

### Fixed
- **Settings → About now always shows the real build version.** It reads the
  in-source `__version__` first; previously it preferred installed-package
  metadata, which could be stale (an editable/long-lived install keeps the
  version it was first installed at).

## [0.1.9] - 2026-06-06

### Changed
- **Prerequisites are now shown inline in the setup form** instead of a
  separate pop-up dialog. Install openconnect-sso, create the config, and see
  what's still missing — all in one place, with no jumping back and forth
  between a checklist and the configuration. (Refactored into a reusable
  `PrereqPanel`; the standalone check is still reachable from the control
  view, and the live progress bar/status carry over.)

## [0.1.8] - 2026-06-05

### Added
- The prerequisite install screen (uv / openconnect-sso) now shows a centered
  message, an **indeterminate progress bar**, and a "this takes a minute" hint
  — instead of a lone line of text in a big empty dialog.

### Changed
- Benign openconnect **Wintun messages** ("Failed to find matching adapter" /
  "Could not open Wintun adapter") are reworded in the connection log.
  openconnect always tries to open an existing adapter, fails, then creates a
  fresh one — so these no longer read like errors.

## [0.1.7] - 2026-06-05

### Changed
- The openconnect prerequisite hint (and the README) now spell out the
  make-or-break install step: in the OpenConnect-GUI installer, **tick the
  “command-line / console version” component** — without it only the GUI is
  installed and the CLI `openconnect.exe` the app needs is missing.

## [0.1.6] - 2026-06-05

### Added
- **2FA token slot** setting: when several authenticator tokens are registered,
  the login page shows one tile per token and validates the code against the
  *selected* one. Pick which tile (1st / 2nd / …) and the app clicks it before
  typing the code. Default leaves the first tile selected, so single-token
  users are unaffected. (Implemented as a position-based click rule in
  openconnect-sso's `config.toml`, since the tile ids are per-account GUIDs.)

### Changed
- The login helper's output now **streams live into the connection log**
  (`openconnect-sso -l INFO`), so a stalled 2FA step is visible instead of the
  log freezing at "Authenticating …".

### Fixed
- Before each fresh connect, orphaned **openconnect-sso browser windows** and a
  **stale openconnect** are cleared — they otherwise pile up ("too many login
  windows") and a half-dead openconnect keeps the Wintun adapter, making the
  next attempt fail with "Failed to register rings".

## [0.1.5] - 2026-06-05

### Fixed
- **`PermissionError [WinError 5]` / `Access denied` on connect**: a misconfigured
  openconnect path pointing at a *folder* (e.g. the Start-Menu shortcut group)
  was passed straight to the OS and rejected. Path resolution now heals a
  folder, a `.lnk`/shortcut, `openconnect-gui.exe`, or any stale/invalid path
  to the real `openconnect.exe` — auto-detecting if needed — so a bad config
  self-heals instead of failing.
- The prerequisites **openconnect check no longer shows a folder as “OK”** (it
  must be an actual executable file).

## [0.1.4] - 2026-06-05

Fixes the "all prerequisites OK but connect fails" class of tester problems —
they came down to an incomplete openconnect, the wrong exe, or a wrong link.

### Fixed
- **Download link** now points to the official OpenConnect-GUI installer
  (`gui.openconnect-vpn.net/download`). The old GitHub-releases link has no
  assets, which is why testers grabbed loose `openconnect.exe` files that
  don't work.
- **Wrong exe**: picking `openconnect-gui.exe` (the graphical client) is now
  auto-corrected to `openconnect.exe` (the CLI engine) in the same folder.
- **`Failed to canonicalize script path`**: openconnect-sso now runs *our*
  configured openconnect (its folder is prepended to PATH), so it uses the
  complete OpenConnect-GUI install (DLLs + routing script) instead of a random
  one on PATH.
- You can now always **save and leave the configuration**: only email + server
  are required; tool paths are checked by the prerequisites dialog, not the
  save — so a stale/empty path no longer traps you.

### Added
- **Routing-script check** in the prerequisites list: warns when
  `vpnc-script-win.js` isn't next to openconnect (i.e. a loose .exe rather
  than a full install) — the cause of the "canonicalize script path" failure.

## [0.1.3] - 2026-06-05

More clean-machine tester fixes.

### Added
- **Paste URL / JSON** to import a TOTP seed (not just QR images): accepts an
  `otpauth://` URI or an authenticator JSON export — incl. **FreeOTP+**, which
  stores the secret as a byte array — so users without a QR export can still
  get their seed in.
- **“Locate openconnect.exe…”** button right in the prerequisites checklist
  (persists the path), for installs auto-detection misses.
- **Close** button in the prerequisites dialog (you can always get out now).
- Failed `openconnect-sso` installs now show the **actual error output**
  (expandable details) instead of just an exit code.

### Fixed
- `openconnect-sso` install failing on very new interpreters (e.g. Python
  3.14): the install now pins a managed **Python 3.12**, which uv fetches.

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
