# sandbox-setup.ps1 — run INSIDE the Windows Sandbox to install ALL the
# prerequisites in one go (uv, openconnect-sso, AND OpenConnect-GUI silently).
#
# Run it in the Sandbox via:
#   powershell -ExecutionPolicy Bypass -File C:\Users\WDAGUtilityAccount\Desktop\testing\sandbox-setup.ps1
#
# After it finishes, just run app\automatic-vpn.exe — every prerequisite
# except your credentials is already in place.

$ErrorActionPreference = 'Stop'

Write-Host "[1/3] Installing uv ..." -ForegroundColor Cyan
Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
# uv lands in %USERPROFILE%\.local\bin — make it usable in this session.
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

Write-Host "[2/3] Installing openconnect-sso (login helper) ..." -ForegroundColor Cyan
uv tool install --python 3.12 --with PyQt6 --with "setuptools<70" openconnect-sso

Write-Host "[3/3] Downloading + silently installing OpenConnect-GUI" `
            "(provides openconnect.exe + DLLs + routing script + Wintun) ..." -ForegroundColor Cyan
$ocUrl = "https://www.infradead.org/openconnect-gui/download/openconnect-gui-1.6.2-win64.exe"
$ocExe = Join-Path $env:TEMP "openconnect-gui-setup.exe"
Invoke-WebRequest -Uri $ocUrl -OutFile $ocExe
# NSIS silent install (/S) to C:\Program Files\OpenConnect-GUI.
Start-Process $ocExe -ArgumentList "/S" -Verb RunAs -Wait

Write-Host ""
if (Test-Path "C:\Program Files\OpenConnect-GUI\openconnect.exe") {
    Write-Host "All prerequisites installed." -ForegroundColor Green
} else {
    Write-Host "OpenConnect-GUI install not detected at the standard path —" -ForegroundColor Yellow
    Write-Host "run $ocExe manually if needed." -ForegroundColor Yellow
}
Write-Host "Next: run app\automatic-vpn.exe (SmartScreen: 'More info' -> 'Run anyway')." -ForegroundColor Green
Write-Host ""
Write-Host "NOTE: the live VPN tunnel may be flaky inside the Sandbox (nested" -ForegroundColor Yellow
Write-Host "networking). Launch + guided setup + the one-time admin task are the" -ForegroundColor Yellow
Write-Host "key things this clean-machine test proves." -ForegroundColor Yellow
