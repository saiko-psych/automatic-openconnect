# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the standalone Windows app (one-file, windowed).
# Build:  pyinstaller packaging/automatic-vpn.spec --noconfirm
# Output: dist/automatic-vpn.exe
import os

_assets = os.path.join(SPECPATH, "..", "src", "automatic_openconnect", "assets")
_icon = os.path.join(_assets, "icon.ico")

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[],
    binaries=[],
    # Bundle the icons so importlib.resources finds them when frozen.
    datas=[(_assets, "automatic_openconnect/assets")],
    hiddenimports=[
        # cv2 is imported lazily inside qr.decode_qr_image, so static
        # analysis misses it — name it explicitly to bundle QR support.
        "cv2",
        # keyring discovers backends via entry points PyInstaller can't see.
        "keyring.backends.Windows",
        "keyring.backends.chainer",
        "keyring.backends.fail",
        "win32ctypes.core",
        "pyotp",
        # pynput's Windows backends are imported dynamically — name them so the
        # global TOTP hotkey works in the frozen exe.
        "pynput",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

# ONE-FOLDER build (not one-file). A one-file exe self-extracts to %TEMP% via
# the PyInstaller bootloader on every launch; when the elevated *Windows Task
# Scheduler service* launches it, that self-extraction silently fails and
# Python never starts (the task reports exit 0 but the backend never runs).
# One-folder ships the exe + its dependencies unpacked in a folder, so the
# Task Scheduler launches the exe directly — no extraction step to fail.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="automatic-vpn",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed; CLI mode writes to the connect log
    disable_windowed_traceback=False,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="automatic-vpn",
)
