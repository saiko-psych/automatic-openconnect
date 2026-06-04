# Clean-machine test via Windows Sandbox

Windows Sandbox is a built-in, disposable, *fresh* Windows (Win 10/11 Pro).
It's the closest thing to a brand-new tester's PC — nothing is installed and
everything resets when you close it. Perfect for verifying that
`automatic-vpn.exe` is self-contained and that the guided setup works from
scratch.

## 1. Enable Windows Sandbox (once)

In an **Administrator** PowerShell:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName "Containers-DisposableClientVM" -All
```

Then **reboot**. (Requires hardware virtualization enabled in the BIOS/UEFI.)
Alternatively: Settings → *Optional features* / *Turn Windows features on or
off* → tick **Windows Sandbox**.

## 2. Build a fresh exe (if you changed code)

```powershell
.build-venv\Scripts\pyinstaller.exe packaging\automatic-vpn.spec --noconfirm
```

`sandbox.wsb` maps the `dist\` folder, so it always picks up the latest build.

## 3. Run the test

Double-click **`sandbox.wsb`**. The Sandbox boots and opens the `app` folder
(with `automatic-vpn.exe`) on the desktop.

Inside the Sandbox:

1. (Fast path) open PowerShell and run the prereq installer:
   ```powershell
   powershell -ExecutionPolicy Bypass -File C:\Users\WDAGUtilityAccount\Desktop\testing\sandbox-setup.ps1
   ```
   It installs `uv` + `openconnect-sso` and opens the OpenConnect-GUI download
   (install that one by hand — it ships `openconnect.exe` + the Wintun driver).
   *(Or do all three steps manually to test the recruitment instructions verbatim.)*
2. Run `app\automatic-vpn.exe`. On SmartScreen: **More info → Run anyway**.
3. Walk through the guided setup; confirm the prerequisites checklist, the
   one-time admin (UAC) task registration, the UI, themes and settings.

## What this proves (and doesn't)

- ✅ The exe launches on a machine with **no Python/deps**.
- ✅ Guided setup + prerequisite detection + the one-time elevated task work.
- ⚠️ The **live VPN tunnel** may be unreliable inside the Sandbox (nested
  networking + Wintun in a VM). For a full end-to-end connection, a real
  second machine is still the gold standard.
