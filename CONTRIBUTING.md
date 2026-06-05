# Contributing

Thanks for your interest in improving **automatic-openconnect**! It's a
community project — issues, ideas and pull requests are all welcome.

## Reporting bugs / requesting features

Use the issue templates (New issue → choose a template):

- **🐞 Bug report** — include the app version, how you installed it, your
  Windows version, and the **connection log** (App → *Show log*).
- **💡 Feature request** — describe the problem first, then your idea.

> **Never paste your password or TOTP seed** into an issue. Redact secrets
> from logs and screenshots. The rotating 6-digit code is harmless; the base32
> **seed** is not. See [SECURITY.md](SECURITY.md).

## Development setup (Windows)

```powershell
git clone https://github.com/saiko-psych/automatic-openconnect
cd automatic-openconnect
.\dev.ps1 setup     # editable .venv with the GUI + QR extras
.\dev.ps1 run       # launch the GUI from source (picks up edits)
.\dev.ps1 test      # run the test suite (pytest)
```

- **Keep logic testable.** Decisions live in `gui_logic.py` / `preflight.py`
  (no Qt import, unit-tested); `gui.py` stays a thin view layer. CI runs on
  Linux without PyQt6, so `gui.py` is only checked via `py_compile` + a local
  run — put anything you want covered into the pure modules.
- **Cross-platform string paths:** the Windows path helpers use `ntpath` so
  the tests pass on the Linux CI. Mock `os.path.isfile/isdir` in tests, not the
  real filesystem.
- **i18n:** user-facing strings are keys in `i18n.py` (EN + DE). Add both.

## Building the standalone .exe

```powershell
.build-venv\Scripts\pyinstaller.exe packaging\automatic-vpn.spec --noconfirm `
    --distpath C:\path\outside\cloud-sync\dist `
    --workpath  C:\path\outside\cloud-sync\build
```

> Build the output **outside any cloud-synced folder** (OneDrive/Nextcloud).
> A sync client locks the ~84 MB exe mid-write and PyInstaller fails at
> `remove_all_resources` (leaving a 0-byte exe).

## Pull requests

1. Branch off `main`.
2. Make the change with matching style; add/update tests.
3. `.\dev.ps1 test` — all green.
4. Open the PR. **Wait for CI (the `tests` workflow) to pass before merging.**

By contributing you agree your work is licensed under the project's
[MIT License](LICENSE) and you'll follow the
[Code of Conduct](CODE_OF_CONDUCT.md).
