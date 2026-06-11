# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.30] - 2026-06-11

### Fixed
- **No more spurious red "timed out" flash during a slow connect (Windows).** The
  GUI's connect window was only ~70 s, which openconnect-sso's embedded login
  browser can exceed when it renders slowly (Skia/GPU stalls) — so the GUI
  flashed "Zeitüberschreitung / timed out" and then "fixed itself" once the
  tunnel came up moments later. Widened the window to 240 s so the **backend's**
  own outcome decides — tunnel up, or a real "FAIL:" — instead of a too-short GUI
  timer. (The connect itself was already succeeding; this only stops the false
  error flash. Genuinely flaky Wintun/auth attempts still surface a real failure.)

## [0.1.29] - 2026-06-10

### Added
- **Headless Linux CLI:** `python -m automatic_openconnect up | down | status`
  brings the tunnel up/down or reports status on a server **without the tray or
  PyQt6** — it works with the plain core install. (No-args still launches the
  tray, which needs `[gui]`.) The termino consumer keeps using the library
  (`with auto_vpn_session(cfg): …`); this is for manual shell control.

### Changed
- **Headless install is now lean (#5).** Moved `PyQt6` and `pynput` out of the
  core dependencies into the `[gui]` extra. `pip install automatic-openconnect`
  now pulls only the headless library (`keyring` + `pyotp`) — no Qt / pynput, so
  `import automatic_openconnect; auto_vpn_session(cfg)` runs on a box with **no
  display** (container / server / the termino consumer). **Desktop & tray users
  must now add the `[gui]` extra:** `pip install "automatic-openconnect[gui]"`
  (add `,qr` for QR-image import). Windows `.exe` is unaffected (bundles PyQt6).

## [0.1.28] - 2026-06-10

### Documentation
- Full **Read the Docs** site (MkDocs Material): per-OS install
  (Windows/Linux/macOS), usage, two-factor/TOTP, security, troubleshooting and a
  developer/architecture page. README slimmed to a landing page that points to
  the docs; the GitHub "About" links to the site. No application code changes
  since 0.1.27 — this tag exists so the docs ship in a release (RTD "stable").

## [0.1.27] - 2026-06-10

### Added
- **Linux & macOS support — a lean system-tray app.** There openconnect-sso does
  the SAML auth AND launches openconnect via passwordless sudo, so there is no
  scheduled-task / elevation dance: `python -m automatic_openconnect` runs a
  small tray (connect/disconnect, a setup dialog for server/group + password +
  TOTP with QR-image import, and a login-autostart toggle). **Linux tested;
  macOS experimental** (written, not yet verified on a real Mac). See the README
  "Setup (Linux / macOS)" section. The Windows app is unchanged.

## [0.1.26] - 2026-06-10

### Added
- A **"Disconnecting …"** status while the tunnel tears down. The teardown
  (schtasks run DOWN + end UP) now runs on a background thread, so the UI shows
  "Disconnecting …" immediately instead of briefly freezing and jumping straight
  to "Disconnected".

## [0.1.25] - 2026-06-10

### Changed
- **Removed the auto-reconnect monitor (and disabled the heartbeat-watchdog) from
  the connect loop.** The monitor re-established the tunnel the instant you clicked
  Disconnect — so it took TWO clicks — and turned a flaky first attempt into a slow
  re-auth loop ("reconnected" after a long wait, most noticeable right after
  re-registering via Configuration → Save). The tunnel is now brought up with one
  clean attempt and simply held until you disconnect, matching the proven
  standalone termino script. Reconnect manually after a network drop.

## [0.1.24] - 2026-06-09

### Fixed
- **THE connect bug — "connected but no internet/traffic" (affected every
  version, incl. 0.1.10).** openconnect.exe was launched without a console
  (CREATE_NO_WINDOW + a windowless launcher), so its `vpnc-script-win.js` —
  which configures DNS + the split-include routes via `cscript` — could not run
  and hung. "Legacy IP route configuration done" never arrived: the tunnel came
  up but routed nothing ("connected" with no internet). openconnect now gets
  its OWN hidden console (CREATE_NEW_CONSOLE + STARTUPINFO SW_HIDE), so the
  script runs and routes are configured. The original termino script always
  worked precisely because it runs under cmd.exe and inherits its console.
  Verified live: routes 143.50.0.0/16 + 193.170.79.0/24 set, uni DNS applied,
  webmail.uni-graz.at reachable through the tunnel.

## [0.1.23] - 2026-06-09

### Changed
- **Simplified the connect back to the proven v0.1.10 single-attempt
  behaviour.** Removed the internal connect-retry added in 0.1.22 — it caused a
  long "connecting…" (it re-authenticated up to 4×) and could briefly show
  "connected" before the tunnel was really up. Kept the 0.1.22 fix that stopped
  the spurious "connection failed" (connect log reset per attempt + the GUI
  only reads the latest attempt).

### Known issue
- "Connected but no internet/email" is openconnect's Wintun route
  configuration not completing (the log ends at "Creating adapter" / "Removed
  orphaned adapter", with no "route configuration done"). Seen on machines with
  a degraded Wintun state or several Wintun/WireGuard VPNs installed
  (Mullvad, WireGuard, Cisco AnyConnect). It is an openconnect/Wintun
  environment issue, not the app — reboot and/or reinstall OpenConnect-GUI to
  refresh the Wintun driver.

## [0.1.22] - 2026-06-09

### Fixed
- **No more spurious "connection failed" flashing before it connects**
  (regression since 0.1.11). The connect log had been switched to APPEND mode,
  so it accumulated every attempt; the elevated task owns the file and the
  non-elevated GUI can't truncate it, so the GUI's step detection kept seeing
  stale "FAIL:" lines from earlier attempts and showed "connection failed" even
  while the current attempt was connecting fine. Now the backend truncates the
  log per attempt (as in 0.1.10), the GUI only considers the latest attempt,
  and a flaky first Wintun-adapter attempt is retried internally (re-auth) so
  it resolves to a clean connect. Verified across repeated runs: no "FAIL:"
  surfaced and the GUI never showed "failed".

## [0.1.21] - 2026-06-09

### Fixed
- **Connect no longer shows a false "connection failed" before connecting**
  (regression since 0.1.14). The elevated task was registered with a
  `-WorkingDirectory` (a hedge for a since-disproven theory) that changed
  openconnect.exe's working directory and broke Wintun adapter creation on the
  FIRST attempt ("Timed out waiting for device query" / "Failed to setup
  adapter"), so it only succeeded on a retry — showing a spurious failure
  first. Removed it (back to the clean v0.1.10 behaviour). Verified locally:
  clean first-attempt connect in ~12-15s, no Wintun error across repeated runs.
  Existing installs are auto-offered a one-click re-register (task version 3).

## [0.1.20] - 2026-06-08

### Fixed
- **"Disconnect when the window is closed" now actually works.** Closing the
  window (the X) honours the exit setting: "disconnect" tears the tunnel down
  and exits; "keep in background" (or nothing connected) minimises to the tray;
  "ask" prompts. Before, closing the X always silently minimised and ignored
  the setting.

## [0.1.19] - 2026-06-08

### Added
- **Auto-reconnect after a network drop.** If `openconnect` dies (e.g. a brief
  Wi-Fi/network outage) while the app owns the tunnel, the background task now
  re-establishes it automatically and unattended (saved credentials + 2FA),
  WITHOUT restarting the conflicting VPN services (no flapping). Backs off
  between attempts and gives up after 15 consecutive failures (the heartbeat
  watchdog keeps running, so you can reconnect manually). Set
  `auto_vpn.auto_reconnect = false` in config.json to disable.

## [0.1.18] - 2026-06-08

### Fixed
- **Connection no longer drops randomly / after a few minutes** (the main
  regression since 0.1.11). The watchdog heartbeat (tells the backend "the GUI
  is alive") was written on the UI thread, and the 0.1.11/0.1.12 timeout
  diagnostics (synchronous schtasks + `diag` subprocess, up to ~45s) could
  block it long enough for the backend to tear down a LIVE tunnel — typically
  while a slow SAML/2FA login was finishing. The heartbeat now runs on its own
  dedicated daemon thread (immune to UI stalls and to a transiently-failing
  process check), and the diagnostics run off the UI thread.
- **Only one instance of the app can run.** Launching it again surfaces the
  existing window instead of opening a second GUI (two GUIs both fired tasks +
  heartbeats and could tear down each other's connection).
- **A single click on the tray icon no longer disconnects** — it only shows the
  window. Connect/Disconnect stay explicit (tray menu + in-app buttons); an
  accidental click used to hard-stop the tunnel.
- **More robust quit/teardown** — quitting no longer skips the
  disconnect/keep-in-background prompt when the liveness check momentarily flakes.

### Known / next
- Auto-reconnect after a brief network outage is **not** yet implemented (the
  backend does not yet restart openconnect if it dies) — planned next.

## [0.1.17] - 2026-06-08

### Added
- **Automatic background-task update.** When the elevated connect/disconnect
  tasks were registered by an older version (e.g. before the on-battery fix in
  0.1.16), the app detects it at startup (stored `task_version`) and offers a
  one-click re-register (one admin prompt) — so existing users get task fixes
  without having to know to open Configuration → Save. Setup also re-registers
  automatically when the stored task definition is outdated.

## [0.1.16] - 2026-06-08

### Fixed
- **Connect now works on laptops running on battery — THE root cause.**
  Microsoft-documented: tasks created via `New-ScheduledTaskSettingsSet`
  default to `DisallowStartIfOnBatteries=$true`, so on a laptop on battery the
  elevated task silently skipped its action (`schtasks /run` returned 0, the
  backend never ran, Connect timed out with an empty log — exactly the tester
  reports). The up/down tasks are now registered with
  `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries`.

### Changed
- Back to a single-file exe (the v0.1.15 one-folder ZIP was a wrong guess; the
  battery setting was the real cause).

> Existing installs: open **Configuration → Save** once (one admin prompt) to
> re-register the task with the new battery setting.

## [0.1.15] - 2026-06-07

### Fixed
- **Root-cause fix for "Connect fires the task but the backend never runs"
  (timed out, empty log) on affected machines.** Proven via launch breadcrumbs:
  the one-file PyInstaller exe self-extracts to %TEMP% on every launch, and that
  self-extraction silently fails when the elevated **Windows Task Scheduler
  service** launches it — so Python never starts (the task still reports exit
  0). The app is now built **one-folder** (no self-extraction): the Task
  Scheduler launches the exe directly.

### Changed
- Distribution is now a **ZIP** (extract, run `automatic-vpn.exe`) instead of a
  bare exe, since the one-folder build ships the exe with its dependencies. A
  proper installer will follow.

## [0.1.14] - 2026-06-07

### Fixed
- **Connect that fired the task but never ran the backend (timed out, empty
  log) on some machines.** Diagnostics traced it to the Task Scheduler
  launching the exe *from the Downloads folder* never starting Python (the very
  same exe run elevated from elsewhere worked fine). Setup now copies the app
  to a stable location (``%LOCALAPPDATA%\Programs\automatic-vpn``), strips
  the Mark-of-the-Web, and registers the elevated task against that copy with a
  pinned working directory. **Re-run setup once** (Configuration → Save) to
  re-register the task to the new location.

## [0.1.13] - 2026-06-07

### Changed
- **Even deeper connect diagnostics.** Every exe launch now writes an entry
  breadcrumb (timestamp, argv, elevation, pid) to `last-entry.log` *before any
  import*, and the CLI dispatch points (`main_cli`, `_cli_up`) breadcrumb too.
  So a failing elevated Scheduled-Task launch shows exactly how far it gets —
  Python never starting (bootloader/launch blocked) vs. reaching the backend.
  The timeout diagnostic now includes these breadcrumbs.

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
