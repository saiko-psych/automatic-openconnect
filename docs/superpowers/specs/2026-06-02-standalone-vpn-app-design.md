# Design: Standalone "Uni Graz VPN" app (Windows)

**Date:** 2026-06-02
**Status:** Approved (design); implementation plan pending
**Component of:** [automatic-openconnect](https://github.com/saiko-psych/automatic-openconnect)

## Context

`automatic-openconnect` currently exposes a library API (`auto_vpn_session`)
and a bare CLI (`python -m automatic_openconnect._windows up/down/status`).
Bringing the tunnel up on Windows requires Administrator rights (Wintun
adapter creation), so today every connect would trigger a UAC prompt — and
the user must hand-craft a `config.json` and store credentials via a
separate interactive CLI.

The user wants instead:

1. An **interactive configuration element**, delivered as a **standalone
   application** (a double-clickable GUI), not a terminal script.
2. A **grant-once** privilege model: the user approves elevation **one
   time**, and connecting afterwards "just works" without a UAC prompt.

The repo already contains the right primitive for grant-once:
`tools/setup-windows-tasks.ps1` registers Windows **Scheduled Tasks** with
`RunLevel Highest`, triggered on-demand. Once registered (one elevation),
`schtasks /run /tn <name>` fires them silently elevated. That script still
references the pre-extraction Termino module names and must be retargeted.

## Decision

Build a **PyQt6 desktop app** that unifies interactive setup and
connect/disconnect control, backed by a Python wrapper around Windows
Scheduled Tasks for the grant-once privilege model.

PyQt6 is already pulled in by the `openconnect-sso` dependency, so the GUI
adds no new heavyweight dependency to the runtime the user already installs.

## Architecture

```
                 ┌─────────────────────────────────────────┐
                 │  gui.py  (PyQt6 app, normal user rights)  │
                 │  ┌───────────────┐    ┌────────────────┐  │
                 │  │ Setup view    │    │ Control view   │  │
                 │  │ (first run /  │    │ Connect /      │  │
                 │  │  no config)   │    │ Disconnect /   │  │
                 │  └──────┬────────┘    │ status poll    │  │
                 │         │             └───────┬────────┘  │
                 └─────────┼─────────────────────┼───────────┘
                           │ writes               │ schtasks /run (no UAC)
              ┌────────────▼─────────┐   ┌────────▼─────────────┐
              │ config.json          │   │ Scheduled Tasks       │
              │ + keyring (secrets)  │   │ AutoOpenconnect-Up    │
              └──────────────────────┘   │ AutoOpenconnect-Down  │
                           ▲              └────────┬─────────────┘
                           │ registered once via   │ runs elevated:
              ┌────────────┴──────────┐            ▼
              │ tasks_windows.py      │   python -m automatic_openconnect._windows up
              │ register/unregister   │
              │ (one UAC: RunAs)      │
              └───────────────────────┘
```

### Components

**`src/automatic_openconnect/gui.py`** — the standalone app.
- *Setup view* (shown when `config.json` is absent or incomplete): form for
  email, server (default `univpn.uni-graz.at`), `openconnect.exe` path
  (pre-filled from auto-detection), `openconnect-sso` path (auto-detected),
  and checkboxes for "stop Cisco / Mullvad during run". Password and TOTP
  base32 seed fields (masked) that write to the keyring via `secrets.py`.
  An **"Einrichten"** button writes `config.json`, stores credentials, and
  invokes `tasks_windows.register()` (the single UAC prompt).
- *Control view*: a large **Connect / Disconnect** toggle and a status
  label driven by a periodic poll of `is_vpn_up()`. Connect fires the
  `AutoOpenconnect-Up` task; Disconnect fires `AutoOpenconnect-Down`.
- A "Settings" affordance to re-open the setup view later.

**`src/automatic_openconnect/tasks_windows.py`** — Scheduled-Task lifecycle
from Python, so the app does not shell out to a separate `.ps1`.
- `register(config) -> None`: builds the task definitions
  (`AutoOpenconnect-Up` → `python -m automatic_openconnect._windows up`,
  `AutoOpenconnect-Down` → `... down`) and registers them **elevated** via
  `Start-Process powershell -Verb RunAs` running an inline registration
  script. This is the one-time UAC prompt.
- `unregister() -> None`: removes the tasks (for a clean uninstall).
- `is_registered() -> bool`: queries `schtasks /query` so the GUI can show
  whether setup is complete.
- `run(task: str) -> None`: `schtasks /run /tn <task>` — no elevation.

**`src/automatic_openconnect/config.py`** (new, small) — load/save the
`config.json` that `_windows.py` already consumes. Single source of truth
for the on-disk schema (`auto_vpn` block).

**`pyproject.toml`** — add a GUI entry point
(`[project.gui-scripts]` → `uni-graz-vpn = automatic_openconnect.gui:main`)
and an optional extra `gui = ["PyQt6>=6.5"]`. Runtime install instructions
in the README already add PyQt6 via `--with`.

**`tools/setup-windows-tasks.ps1`** — retarget from `utils.auto_vpn_win` /
`main.py` to `python -m automatic_openconnect._windows up|down`. Kept as a
power-user / scriptable alternative to the GUI's in-app registration; both
register the **same** task names so they don't diverge.

### Data flow

1. **First launch** → no `config.json` → Setup view.
2. User fills the form, clicks "Einrichten":
   - `config.py.save()` writes `config.json` (next to the app / in a known
     per-user location — see Open questions).
   - `secrets.py.set_uni_login_password()` / `set_uni_totp_secret()` store
     credentials in the keyring.
   - `tasks_windows.register(config)` → **one UAC prompt** → two on-demand
     elevated tasks exist.
3. **Connect** → `tasks_windows.run("AutoOpenconnect-Up")` → the elevated
   task runs `_windows up`, which authenticates via openconnect-sso and
   brings up `openconnect.exe`. No UAC.
4. **Status** → GUI polls `is_vpn_up()` every few seconds, updates the label
   and the toggle.
5. **Disconnect** → `tasks_windows.run("AutoOpenconnect-Down")`.

### Error handling

- Setup validates: email non-empty, both binaries resolvable
  (`shutil.which` / configured path), `config.toml` selectors present.
  Missing items are surfaced inline in the form, not as exceptions.
- `register()` failure (user cancels the UAC prompt, or PowerShell errors)
  → the GUI stays in Setup view with a clear message; nothing half-written
  is left as "done" (config.json is only marked complete once tasks exist).
- `run()` surfaces a non-zero `schtasks` exit as a GUI error banner.
- The underlying `_windows.py` already raises `VPNError` with actionable
  messages; the task console (visible by design) shows them.

### Testing

- `tasks_windows.py`: unit-test the command construction (task XML / argv,
  `schtasks` invocations) with `subprocess` mocked — mirrors the existing
  mocked style in `tests/test_windows.py`. No real task registration in CI.
- `config.py`: round-trip load/save tests on a temp file.
- `gui.py`: logic-only tests where practical (view selection given
  config/registration state); no live Qt event-loop test in CI (CI is
  Linux-only and headless). Keep GUI logic thin and delegate to the testable
  modules.
- Manual end-to-end on the user's Windows machine: setup (one UAC), connect
  (no UAC), verify `webmail.uni-graz.at` reachable via VPN IP, disconnect.

## Consequences

- **Easier:** one-time setup; daily connect is a single click, no UAC.
- **Easier:** config and credentials are entered in one interactive place.
- **Harder / to revisit:** the app must keep the GUI, the `_windows.py`
  CLI, and the `.ps1` script in sync on task names and module paths — the
  shared `tasks_windows.py` definitions mitigate this by being the single
  source for the GUI path.
- **Out of scope (later phases):** PyInstaller single-`.exe` packaging,
  system-tray operation, autostart, macOS/Linux GUI parity.

## Open questions (resolve during planning)

1. **`config.json` location.** Next to the app vs. a per-user dir
   (`%APPDATA%\automatic-openconnect\config.json`). Leaning per-user
   `%APPDATA%` so the app works regardless of where it is launched, and so
   the file is naturally outside any git checkout. The `_windows.py` CLI
   defaults to `config.json` in cwd — `tasks_windows.register` will pass an
   explicit `--config <abspath>` to the task so both agree.
2. **Elevation UX.** Single combined UAC for both task registrations
   (one elevated PowerShell registering both) — yes, to keep it to exactly
   one prompt.

## Privacy / gitignore note

`config.json` and any per-user data must never be committed. The repo's
`.gitignore` already excludes `config.json`, `config.toml`, `*.local.json`,
`.env*`, and AI-assistant files. The per-user `%APPDATA%` location keeps
config out of the checkout entirely. No new private files are introduced.
```
