# sandbox-setup.ps1 — run INSIDE the Windows Sandbox to install the
# scriptable prerequisites quickly, then install OpenConnect-GUI by hand.
#
# Run it in the Sandbox via:
#   powershell -ExecutionPolicy Bypass -File C:\Users\WDAGUtilityAccount\Desktop\testing\sandbox-setup.ps1
#
# This mirrors the steps a real tester follows (see the recruitment text) —
# so it also doubles as a check that those instructions actually work.

$ErrorActionPreference = 'Stop'

Write-Host "[1/3] Installing uv ..." -ForegroundColor Cyan
Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
# uv lands in %USERPROFILE%\.local\bin — make it usable in this session.
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

Write-Host "[2/3] Installing openconnect-sso (login helper) ..." -ForegroundColor Cyan
uv tool install --with PyQt6 --with "setuptools<70" openconnect-sso

Write-Host "[3/3] Opening the OpenConnect-GUI download (install it with the" `
            "official installer: it provides openconnect.exe + DLLs + the" `
            "routing script + the Wintun driver) ..." -ForegroundColor Cyan
Start-Process "https://gui.openconnect-vpn.net/download/"

Write-Host ""
Write-Host "Prereqs (scriptable part) done. Next:" -ForegroundColor Green
Write-Host "  1. Install OpenConnect-GUI from the page that just opened."
Write-Host "  2. Run app\automatic-vpn.exe on the Desktop."
Write-Host "  3. SmartScreen: 'More info' -> 'Run anyway' (the exe is unsigned)."
Write-Host ""
Write-Host "NOTE: the live VPN tunnel may be flaky inside the Sandbox (nested" -ForegroundColor Yellow
Write-Host "networking). Launch + guided setup + the one-time admin task are the" -ForegroundColor Yellow
Write-Host "key things this clean-machine test proves." -ForegroundColor Yellow
