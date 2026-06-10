# For developers

## Architecture

The package is a thin automation layer over two external tools — it implements
no crypto or SAML of its own:

```
GUI (Windows)  /  tray (Linux+macOS)
        │
        ├── openconnect-sso  → SAML/Keycloak login in an embedded browser,
        │                       auto-filled from the OS keyring
        └── openconnect      → builds the Cisco AnyConnect tunnel
```

Two deliberately different shapes per platform:

| | Windows | Linux / macOS |
|---|---------|---------------|
| UI | full PyQt6 GUI (`gui.py`) | lean tray (`_posix_tray.py`) |
| Backend | `_windows.py` | `_linux.py` (library) / direct openconnect-sso |
| Elevation | grant-once **Scheduled Task** (Wintun needs admin; no `sudo`) | passwordless **sudo** rule (openconnect-sso launches openconnect) |
| Launch | `automatic-vpn.exe` (PyInstaller) | `python -m automatic_openconnect` / CI binary |

The lean tray exists because on Linux/macOS `openconnect-sso` already does auth
**and** launches `openconnect` via sudo — so there's nothing to elevate or
orchestrate. On Windows neither is true, hence the heavier machinery.

## Code map

| Module | Role |
|--------|------|
| `__main__.py` | platform dispatch: Windows → `gui.run()`, else → `_posix_tray.run()` |
| `gui.py` | Windows GUI (control/setup/settings views, tray) |
| `_windows.py` | Windows backend: auth, `_start_tunnel`, the `up`/`down` CLI |
| `tasks_windows.py` | Scheduled-Task lifecycle (register/run/end) — grant-once UAC |
| `autostart.py` | Windows login autostart (HKCU `…\Run`) |
| `_posix_tray.py` | Linux/macOS tray: connect/disconnect, setup dialog, autostart |
| `_linux.py` | headless Linux library (`auto_vpn_session`) |
| `config.py` / `secrets.py` | config file + keyring access |
| `preflight.py` | prerequisite checks + the openconnect-sso `config.toml` |

## Build & run from source

```bash
uv venv && source .venv/bin/activate   # (PowerShell: .venv\Scripts\activate)
uv pip install -e ".[dev]"             # add ,qr for QR import; gui is auto on Linux/macOS
python -m automatic_openconnect        # GUI (Windows) / tray (Linux/macOS)
```

Run the tests (offscreen Qt, no real window/tunnel):

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

## Packaging & releases

- **Windows `.exe`** is built from `packaging/automatic-vpn.spec`
  (PyInstaller, one-file, `console=False`). Build output must go **outside**
  any cloud-synced folder.
- **Linux/macOS binaries** are built in CI:
  `.github/workflows/release-posix.yml` runs PyInstaller of
  `packaging/posix_entry.py` on `ubuntu-latest` + `macos-latest` for every `v*`
  tag and attaches the binaries to the GitHub release (alongside the Windows
  `.exe`).
- `tests.yml` runs the suite on Linux for every push/PR.

## Hard-won lessons

A few non-obvious things that bit us (and are now guard-railed):

- **openconnect needs a console.** Launched with `CREATE_NO_WINDOW` from a
  windowless parent, its route-config script (`cscript`) hangs → tunnel up but no
  routes. It gets a **hidden** console (`CREATE_NEW_CONSOLE` + `SW_HIDE`) instead.
- **No auto-reconnect monitor.** It reconnected the instant the user clicked
  Disconnect (→ two clicks) and turned a flaky first attempt into a slow re-auth
  loop. The backend now brings the tunnel up once and just holds it.
- **Scheduled tasks default to `DisallowStartIfOnBatteries`** — set
  `-AllowStartIfOnBatteries` or a laptop on battery silently skips the action.
- **Never block the Qt UI thread** with `schtasks`/`subprocess` — run them on a
  daemon thread.

## Contributing

PRs welcome. Keep it lean — prefer leaning on `openconnect-sso`/`openconnect`
over re-implementing. Run the tests before pushing. Issues + logs:
[github.com/saiko-psych/automatic-openconnect/issues](https://github.com/saiko-psych/automatic-openconnect/issues).
