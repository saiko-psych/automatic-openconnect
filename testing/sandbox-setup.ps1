# sandbox-setup.ps1 — run INSIDE the Windows Sandbox to install the
# prerequisites quickly.
#
# Run it in the Sandbox via:
#   powershell -ExecutionPolicy Bypass -File C:\Users\WDAGUtilityAccount\Desktop\testing\sandbox-setup.ps1
#
# It installs uv + openconnect-sso, then downloads and LAUNCHES the
# OpenConnect-GUI installer. IMPORTANT: in that installer, tick the
# "console version" component so the CLI openconnect.exe gets installed —
# the app needs the CLI, not the GUI.

$ErrorActionPreference = 'Stop'

Write-Host "[1/3] Installing uv ..." -ForegroundColor Cyan
Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
# uv lands in %USERPROFILE%\.local\bin — make it usable in this session.
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"

Write-Host "[2/3] Installing openconnect-sso (login helper) ..." -ForegroundColor Cyan
uv tool install --python 3.12 --with PyQt6 --with "setuptools<70" openconnect-sso

Write-Host "[3/3] Downloading the OpenConnect-GUI installer ..." -ForegroundColor Cyan
$ocUrl = "https://www.infradead.org/openconnect-gui/download/openconnect-gui-1.6.2-win64.exe"
$ocExe = Join-Path $env:USERPROFILE "Downloads\openconnect-gui-setup.exe"
Invoke-WebRequest -Uri $ocUrl -OutFile $ocExe
Write-Host "Launching the installer — TICK the 'console version' component!" -ForegroundColor Yellow
Start-Process $ocExe

Write-Host ""
Write-Host "After installing (with the console version ticked):" -ForegroundColor Green
Write-Host "  run app\automatic-vpn.exe  (SmartScreen: More info -> Run anyway)"
Write-Host ""
Write-Host "NOTE: the live VPN tunnel can be flaky inside the Sandbox (nested networking)." -ForegroundColor Yellow
