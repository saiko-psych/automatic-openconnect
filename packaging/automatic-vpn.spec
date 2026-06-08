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
        # QtNetwork is imported lazily (single-instance QLocalServer/Socket).
        "PyQt6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

# One-file, windowed. (The real cause of "task fires but backend never runs"
# was the Scheduled Task's default DisallowStartIfOnBatteries=$true — a laptop
# on battery silently skipped the action — NOT the one-file format; fixed in
# tasks_windows.build_register_script. So the convenient single exe stays.)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="automatic-vpn",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # windowed; CLI mode writes to the connect log
    disable_windowed_traceback=False,
    icon=_icon,
)
