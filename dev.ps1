# dev.ps1 — developer workflow helper for automatic-openconnect
# ---------------------------------------------------------------------------
# Fast inner loop: install the package *editable* into a local .venv ONCE,
# then run straight from source so code changes need no reinstall. Reserve the
# slow `uv tool install` for verifying the real, packaged executable.
#
# Usage:
#   .\dev.ps1 setup       # create .venv + editable install (run once)
#   .\dev.ps1 run         # launch the GUI from source (picks up edits live)
#   .\dev.ps1 test        # run the test suite
#   .\dev.ps1 reinstall   # rebuild the real uv tool (kills the running app,
#                         # busts the build cache) — for final verification
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'run', 'test', 'reinstall')]
    [string]$Task = 'run'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Venv = Join-Path $Root '.venv'
$VenvPy = Join-Path $Venv 'Scripts\python.exe'

# Extras the GUI needs but that aren't hard dependencies (heavyweight / optional).
$Extras = '.[gui,qr]'

function Invoke-Setup {
    if (-not (Test-Path $VenvPy)) {
        Write-Host "Creating .venv ..." -ForegroundColor Cyan
        uv venv $Venv
    }
    Write-Host "Editable install ($Extras + pynput) ..." -ForegroundColor Cyan
    uv pip install --python $VenvPy -e $Extras pynput
    Write-Host "Done. Run the app with:  .\dev.ps1 run" -ForegroundColor Green
}

function Invoke-Run {
    if (-not (Test-Path $VenvPy)) { Invoke-Setup }
    Write-Host "Launching GUI from source ..." -ForegroundColor Cyan
    & $VenvPy -m automatic_openconnect
}

function Invoke-Test {
    if (-not (Test-Path $VenvPy)) { Invoke-Setup }
    & $VenvPy -m pytest -q
}

function Invoke-Reinstall {
    # The installed launcher locks its .exe while the app runs, and uv caches
    # the built wheel — so kill the app and force a fresh build.
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessName -like '*automatic-vpn*' -or
            $_.Path -like '*automatic-openconnect*'
        } | ForEach-Object {
            Write-Host "Stopping $($_.ProcessName) ($($_.Id)) ..." -ForegroundColor Yellow
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Milliseconds 500
    uv cache clean automatic-openconnect
    uv tool install --force --reinstall --refresh `
        --with PyQt6 --with "setuptools<70" --with opencv-python-headless `
        --from $Root automatic-openconnect
}

switch ($Task) {
    'setup'     { Invoke-Setup }
    'run'       { Invoke-Run }
    'test'      { Invoke-Test }
    'reinstall' { Invoke-Reinstall }
}
