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
                             QPushButton, QComboBox, QFileDialog, QMessageBox)
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


# --- autostart (login) --------------------------------------------------

def _autostart_path() -> Path:
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "LaunchAgents"
                / "at.uni-graz.automatic-openconnect.plist")
    return (Path.home() / ".config" / "autostart"
            / "automatic-openconnect.desktop")


def autostart_enabled() -> bool:
    return _autostart_path().exists()


def set_autostart(enable: bool) -> None:
    """Create/remove the login autostart entry. Launches THIS interpreter with
    ``-m automatic_openconnect`` (so a venv install keeps working)."""
    p = _autostart_path()
    if not enable:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    exe = sys.executable
    if sys.platform == "darwin":
        p.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0"><dict>\n'
            '  <key>Label</key><string>at.uni-graz.automatic-openconnect</string>\n'
            '  <key>ProgramArguments</key>\n'
            f'  <array><string>{exe}</string><string>-m</string>'
            '<string>automatic_openconnect</string></array>\n'
            '  <key>RunAtLoad</key><true/>\n'
            '</dict></plist>\n')
    else:
        p.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=automatic VPN (Uni Graz)\n"
            f"Exec={exe} -m automatic_openconnect\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-KDE-autostart-phase=2\n")


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


def _totp_secret_from_uri(uri: str) -> str:
    """Extract the Base32 TOTP secret from a scanned QR payload.

    Handles both the plain ``otpauth://totp/...?secret=BASE32`` form and
    Google Authenticator's ``otpauth-migration://offline?data=<base64 protobuf>``
    export (first account only). Raises ValueError if it can't.
    """
    import base64
    import urllib.parse as up

    uri = (uri or "").strip()
    if uri.startswith("otpauth://"):
        q = up.parse_qs(up.urlparse(uri).query)
        sec = (q.get("secret") or [""])[0]
        if sec:
            return sec.replace(" ", "").upper()
        raise ValueError("otpauth-URI ohne secret-Parameter.")
    if uri.startswith("otpauth-migration://"):
        data = up.unquote(uri.split("data=", 1)[1])
        raw = base64.b64decode(data)
        # Minimal protobuf walk: outer field 1 (OtpParameters), inner field 1
        # (secret bytes) → Base32. Works for the common single-account export.
        pos = 0
        if raw[pos] != 0x0A:
            raise ValueError("Unerwartetes Migrations-Format.")
        pos += 2                       # outer tag + length byte
        if raw[pos] != 0x0A:
            raise ValueError("Kein secret-Feld im Export.")
        pos += 1
        slen = raw[pos]; pos += 1
        secret_bytes = raw[pos:pos + slen]
        return base64.b32encode(secret_bytes).decode().rstrip("=")
    raise ValueError("Kein TOTP-QR-Code (otpauth / otpauth-migration) erkannt.")


def _totp_secret_from_image(path: str) -> str:
    """Decode a QR-code image file → TOTP Base32 secret. Needs the ``qr`` extra
    (``pip install -e '.[qr]'`` → opencv). Raises with a clear hint otherwise."""
    try:
        import cv2  # from the [qr] extra (opencv-python-headless)
    except ImportError:
        raise ValueError("QR-Upload braucht opencv: pip install -e '.[qr]'")
    img = cv2.imread(path)
    if img is None:
        raise ValueError("Bild konnte nicht gelesen werden.")
    data, _pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
    if not data:
        raise ValueError("Kein QR-Code im Bild gefunden.")
    return _totp_secret_from_uri(data)


class SetupDialog(QDialog):
    """Configure everything via the GUI: e-mail + server + auth group (saved to
    config.json) and password + TOTP secret (saved to the openconnect-sso
    keyring). TOTP can be typed or imported from a QR-code image."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uni Graz VPN — Einrichtung")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("E-Mail (Uni Graz):"))
        self.email = QLineEdit(cfg.get("user_email", ""))
        lay.addWidget(self.email)

        lay.addWidget(QLabel("Server:"))
        self.server = QLineEdit(cfg.get("server", "univpn.uni-graz.at"))
        lay.addWidget(self.server)

        lay.addWidget(QLabel("Gruppe (authgroup):"))
        self.group = QComboBox()
        self.group.setEditable(True)
        self.group.addItems(["Studierende", "Bedienstete"])
        self.group.setCurrentText(cfg.get("authgroup", "Studierende"))
        lay.addWidget(self.group)

        lay.addWidget(QLabel("Passwort (leer = unverändert):"))
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText("nur ändern, wenn nötig")
        lay.addWidget(self.pw)

        lay.addWidget(QLabel("TOTP-Secret (Base32, leer = unverändert):"))
        totp_row = QHBoxLayout()
        self.totp = QLineEdit()
        self.totp.setPlaceholderText("z. B. JBSWY3DPEHPK3PXP")
        totp_row.addWidget(self.totp)
        qr_btn = QPushButton("QR-Bild …")
        qr_btn.clicked.connect(self._load_qr)
        totp_row.addWidget(qr_btn)
        lay.addLayout(totp_row)

        row = QHBoxLayout()
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Speichern")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        self.email.setFocus()

    def _load_qr(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "QR-Code-Bild wählen", "",
            "Bilder (*.png *.jpg *.jpeg *.bmp *.gif);;Alle Dateien (*)")
        if not path:
            return
        try:
            self.totp.setText(_totp_secret_from_image(path))
            QMessageBox.information(self, "TOTP", "TOTP-Secret aus QR gelesen.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "QR-Fehler", str(exc))

    def save(self) -> None:
        """Persist e-mail/server/group to config.json and password/TOTP to the
        keyring (only the fields that were filled in)."""
        email = self.email.text().strip()
        data = cfgmod.load_config()
        av = data.setdefault("auto_vpn", {})
        av["user_email"] = email
        av["server"] = self.server.text().strip() or "univpn.uni-graz.at"
        av["authgroup"] = self.group.currentText().strip()
        cfgmod.save_config(data)
        if self.pw.text() or self.totp.text():
            import keyring
            if self.pw.text():
                keyring.set_password(SSO_KEYRING, email, self.pw.text())
            if self.totp.text():
                keyring.set_password(SSO_KEYRING, f"totp/{email}",
                                     self.totp.text().replace(" ", "").upper())


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
    setup_act = menu.addAction("Einrichten / Zugangsdaten …")
    autostart_act = menu.addAction("Autostart beim Login")
    autostart_act.setCheckable(True)
    autostart_act.setChecked(autostart_enabled())
    quit_act = menu.addAction("Beenden")
    tray.setContextMenu(menu)
    tray.show()

    def toggle_autostart(checked):
        try:
            set_autostart(checked)
            tray.showMessage(
                "VPN",
                "Autostart aktiviert." if checked else "Autostart deaktiviert.",
                QSystemTrayIcon.MessageIcon.Information, 2500)
        except Exception as exc:  # noqa: BLE001
            autostart_act.setChecked(autostart_enabled())
            tray.showMessage("VPN", f"Autostart-Fehler: {exc}",
                             QSystemTrayIcon.MessageIcon.Critical, 4000)

    autostart_act.toggled.connect(toggle_autostart)

    state = {"s": OFF, "blink": False, "dlg_shown": False}

    def do_connect():
        if not _vpn_cfg().get("user_email"):
            show_setup()            # can't connect without an e-mail
            return
        state["s"] = CONNECTING
        state["dlg_shown"] = False
        start_vpn()

    def do_disconnect():
        stop_vpn()
        state["s"] = OFF

    def show_setup():
        dlg = SetupDialog(_vpn_cfg())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                dlg.save()
                tray.showMessage("VPN", "Einstellungen gespeichert.",
                                 QSystemTrayIcon.MessageIcon.Information, 3000)
            except Exception as exc:  # noqa: BLE001
                tray.showMessage("VPN", f"Fehler beim Speichern: {exc}",
                                 QSystemTrayIcon.MessageIcon.Critical, 5000)

    connect_act.triggered.connect(do_connect)
    disconnect_act.triggered.connect(do_disconnect)
    setup_act.triggered.connect(show_setup)
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
                    show_setup()
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

    # First run with no e-mail configured → open setup right away so the user
    # never faces a tray that silently can't connect.
    if not _vpn_cfg().get("user_email"):
        show_setup()

    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.exec()
