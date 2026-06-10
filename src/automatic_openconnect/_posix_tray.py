# -*- coding: utf-8 -*-
"""Lean Linux/macOS system-tray app for the Uni-Graz VPN.

Why this is so much smaller than the Windows path: on Linux/macOS
``openconnect-sso`` does the whole job — it runs the SAML auth in its embedded
browser AND launches ``openconnect`` itself via passwordless ``sudo``. So there
is no scheduled-task / grant-once-UAC dance and nothing to launch ourselves;
this module is just a tray that runs openconnect-sso, polls the tunnel
interface for status, and tears it down. It mirrors the proven standalone
``vpn-tray.py`` prototype, but reads e-mail/server/group from the app config.

Run (from a source checkout):  ``python -m automatic_openconnect``  on Linux/macOS.

Credentials live in the OS keyring under openconnect-sso's own schema
(``keyring.get_password("openconnect-sso", email)`` for the password,
``"totp/"+email`` for the TOTP secret); the tray offers a dialog to set them.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import os
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QDialog,
                             QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import QTimer, Qt

from . import config as cfgmod

# openconnect-sso's keyring namespace — must match exactly or it won't find
# the credentials it auto-fills with.
SSO_KEYRING = "openconnect-sso"

OFF, CONNECTING, ON, FAILED = range(4)

# Per-run log so the user can `tail -f` it (overwritten each connect, like the
# prototype's /tmp/vpn.log).
LOG_PATH = str(Path(tempfile.gettempdir()) / "automatic-openconnect-vpn.log")


# --- VPN control (thin wrappers around openconnect-sso) -----------------

def _vpn_cfg() -> dict:
    return (cfgmod.load_config().get("auto_vpn") or {})


def _tunnel_up() -> bool:
    """True if a VPN tunnel interface is up.

    Linux: openconnect creates ``tun0``. macOS: it creates a ``utunN`` whose
    index we can't predict, so we fall back to 'is openconnect running'.
    """
    try:
        if sys.platform == "darwin":
            return subprocess.run(["pgrep", "-x", "openconnect"],
                                  capture_output=True).returncode == 0
        return subprocess.run(["ip", "link", "show", "tun0"],
                              capture_output=True).returncode == 0
    except (FileNotFoundError, OSError):
        return False


def _sso_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-f", "openconnect-sso"],
                              capture_output=True).returncode == 0
    except (FileNotFoundError, OSError):
        return False


def start_vpn() -> None:
    """Launch openconnect-sso (auth + tunnel) in the background."""
    cfg = _vpn_cfg()
    email = cfg.get("user_email", "")
    server = cfg.get("server", "univpn.uni-graz.at")
    authgroup = cfg.get("authgroup", "")
    sso = cfg.get("openconnect_sso_path") or "openconnect-sso"
    cmd = [sso, "--server", server]
    if email:
        cmd += ["--user", email]
    if authgroup:
        cmd += ["--authgroup", authgroup]
    # Detached so it survives even if the tray is closed (like the prototype);
    # openconnect keeps the tunnel until explicitly stopped.
    with open(LOG_PATH, "w") as log:
        subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)


def stop_vpn() -> None:
    """Tear the tunnel down. ``sudo killall openconnect`` needs the passwordless
    sudoers rule (see the Linux setup docs); also kill any lingering sso."""
    for cmd in (["sudo", "killall", "openconnect"],
                ["pkill", "-f", "openconnect-sso"]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=10)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass


# --- tray icon ----------------------------------------------------------

def _icon(color: str, hollow: bool = False) -> QIcon:
    px = QPixmap(22, 22)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(0, 0, 0, 0) if hollow else QColor(color))
    p.setPen(QColor(color))
    p.drawEllipse(3, 3, 16, 16)
    p.end()
    return QIcon(px)


class CredentialDialog(QDialog):
    """Set the openconnect-sso keyring entries (password + optional TOTP)."""

    def __init__(self, email: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uni Graz VPN — Zugangsdaten")
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Zugangsdaten im Schlüsselbund speichern:"))
        lay.addWidget(QLabel("E-Mail (Uni Graz):"))
        self.email = QLineEdit(email)
        lay.addWidget(self.email)
        lay.addWidget(QLabel("Passwort:"))
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self.pw)
        lay.addWidget(QLabel("TOTP-Secret (Base32, optional):"))
        self.totp = QLineEdit()
        lay.addWidget(self.totp)
        row = QHBoxLayout()
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Speichern")
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        self.pw.setFocus()


def _save_credentials(email: str, password: str, totp: str) -> None:
    import keyring
    if password:
        keyring.set_password(SSO_KEYRING, email, password)
    if totp:
        keyring.set_password(SSO_KEYRING, f"totp/{email}", totp.replace(" ", ""))


def run() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        sys.stderr.write("No system tray available on this desktop.\n")
        return 1

    ic_off = _icon("#666666")
    ic_on = _icon("#00cc00")
    ic_yellow = _icon("#ffcc00")
    ic_yellow_dim = _icon("#ffcc00", hollow=True)
    ic_red = _icon("#cc0000")

    tray = QSystemTrayIcon(ic_off)
    menu = QMenu()
    status_act = menu.addAction("VPN: …")
    status_act.setEnabled(False)
    menu.addSeparator()
    connect_act = menu.addAction("Verbinden")
    disconnect_act = menu.addAction("Trennen")
    menu.addSeparator()
    creds_act = menu.addAction("Zugangsdaten ändern …")
    quit_act = menu.addAction("Beenden")
    tray.setContextMenu(menu)
    tray.show()

    state = {"s": OFF, "blink": False, "dlg_shown": False}

    def do_connect():
        state["s"] = CONNECTING
        state["dlg_shown"] = False
        start_vpn()

    def do_disconnect():
        stop_vpn()
        state["s"] = OFF

    def show_creds():
        email = _vpn_cfg().get("user_email", "")
        dlg = CredentialDialog(email)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                _save_credentials(dlg.email.text().strip(),
                                  dlg.pw.text(), dlg.totp.text())
                tray.showMessage("VPN", "Zugangsdaten gespeichert.",
                                 QSystemTrayIcon.MessageIcon.Information, 3000)
            except Exception as exc:  # noqa: BLE001
                tray.showMessage("VPN", f"Fehler: {exc}",
                                 QSystemTrayIcon.MessageIcon.Critical, 4000)

    connect_act.triggered.connect(do_connect)
    disconnect_act.triggered.connect(do_disconnect)
    creds_act.triggered.connect(show_creds)
    quit_act.triggered.connect(app.quit)

    def on_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if _tunnel_up():
                do_disconnect()
            elif state["s"] != CONNECTING:
                do_connect()

    tray.activated.connect(on_activated)

    def tick():
        if _tunnel_up():
            state["s"] = ON
            state["dlg_shown"] = False
            tray.setIcon(ic_on)
            tray.setToolTip("VPN: Verbunden — Klick zum Trennen")
            status_act.setText("🟢 Verbunden")
            connect_act.setEnabled(False)
            disconnect_act.setEnabled(True)
        elif state["s"] == CONNECTING:
            if _sso_running():
                state["blink"] = not state["blink"]
                tray.setIcon(ic_yellow if state["blink"] else ic_yellow_dim)
                tray.setToolTip("VPN: Verbinde …")
                status_act.setText("🟡 Verbinde …")
                connect_act.setEnabled(False)
                disconnect_act.setEnabled(True)
            else:
                state["s"] = FAILED
                tray.setIcon(ic_red)
                tray.setToolTip("VPN: Fehlgeschlagen — Klick für neuen Versuch")
                status_act.setText("🔴 Fehlgeschlagen")
                connect_act.setEnabled(True)
                disconnect_act.setEnabled(False)
                if not state["dlg_shown"]:
                    state["dlg_shown"] = True
                    show_creds()
        elif state["s"] == FAILED:
            tray.setIcon(ic_red)
            connect_act.setEnabled(True)
            disconnect_act.setEnabled(False)
        else:
            state["s"] = OFF
            tray.setIcon(ic_off)
            tray.setToolTip("VPN: Getrennt — Klick zum Verbinden")
            status_act.setText("⚪ Getrennt")
            connect_act.setEnabled(True)
            disconnect_act.setEnabled(False)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1000)
    tick()

    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()
