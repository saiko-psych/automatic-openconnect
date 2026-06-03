# src/automatic_openconnect/gui.py
# -*- coding: utf-8 -*-
"""Standalone PyQt6 app for the Uni-Graz VPN.

Two views, chosen by gui_logic.choose_view():
  * Setup   — collect config + credentials, register the elevated tasks
              (one UAC prompt) via tasks_windows.register().
  * Control — Connect / Disconnect buttons firing the on-demand tasks
              (no UAC), with a status label polling is_vpn_up().

This module is intentionally thin; testable decisions live in gui_logic.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFormLayout, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

from . import config as cfgmod
from . import gui_logic as gl
from . import tasks_windows as tw
from ._windows import is_vpn_up, connect_log_path
from .secrets import set_uni_login_password, set_uni_totp_secret

# How many 3-second status polls to wait for the tunnel before declaring
# the connect attempt failed (~36 s — auth + tunnel usually take 10-25 s).
_CONNECT_TIMEOUT_TICKS = 12


class SetupView(QWidget):
    def __init__(self, on_done):
        super().__init__()
        self._on_done = on_done
        form = QFormLayout(self)

        existing = (cfgmod.load_config().get("auto_vpn") or {})
        self.email = QLineEdit(existing.get("user_email", ""))
        self.server = QLineEdit(existing.get("server", "univpn.uni-graz.at"))
        self.oc = QLineEdit(existing.get("openconnect_path") or gl.detect_openconnect())
        self.sso = QLineEdit(existing.get("openconnect_sso_path") or gl.detect_openconnect_sso())
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.totp = QLineEdit()
        self.totp.setEchoMode(QLineEdit.EchoMode.Password)
        self.stop_cisco = QCheckBox("Cisco Secure Client während Verbindung stoppen")
        self.stop_cisco.setChecked(existing.get("stop_cisco_during_run", True))
        self.stop_mullvad = QCheckBox("Mullvad während Verbindung stoppen")
        self.stop_mullvad.setChecked(existing.get("stop_mullvad_during_run", True))

        form.addRow("E-Mail", self.email)
        form.addRow("Server", self.server)
        form.addRow("openconnect.exe", self.oc)
        form.addRow("openconnect-sso", self.sso)
        self.pw.setPlaceholderText("nur ausfüllen, um es zu ändern")
        self.totp.setPlaceholderText("base32-Seed — nur ausfüllen, um ihn zu ändern")
        form.addRow("Passwort", self.pw)
        form.addRow("TOTP-Seed", self.totp)
        form.addRow(self.stop_cisco)
        form.addRow(self.stop_mullvad)

        btn = QPushButton("Einrichten (einmaliger Admin-Dialog)")
        btn.clicked.connect(self._submit)
        form.addRow(btn)

    def _submit(self):
        fields = {
            "email": self.email.text(), "server": self.server.text(),
            "openconnect_path": self.oc.text(),
            "openconnect_sso_path": self.sso.text(),
        }
        errors = gl.validate_setup_form(fields)
        if errors:
            QMessageBox.warning(self, "Bitte korrigieren", "\n".join(errors))
            return

        data = gl.build_auto_vpn_config(
            email=fields["email"], server=fields["server"],
            openconnect_path=fields["openconnect_path"],
            openconnect_sso_path=fields["openconnect_sso_path"],
            stop_cisco=self.stop_cisco.isChecked(),
            stop_mullvad=self.stop_mullvad.isChecked())
        path = cfgmod.save_config(data)

        try:
            tw.register(sys.executable, str(path))
        except Exception as exc:  # VPNError or subprocess failure
            QMessageBox.critical(self, "Setup fehlgeschlagen", str(exc))
            return

        # Commit credentials only once the elevated task actually exists.
        if self.pw.text():
            set_uni_login_password(fields["email"], self.pw.text())
        if self.totp.text():
            set_uni_totp_secret(fields["email"], self.totp.text().replace(" ", ""))

        QMessageBox.information(self, "Fertig",
                                "Eingerichtet. Verbinden braucht jetzt keinen Admin-Dialog mehr.")
        self._on_done()


class ControlView(QWidget):
    def __init__(self, on_settings):
        super().__init__()
        self._on_settings = on_settings
        self._connecting = 0   # >0 while a connect attempt is in flight
        layout = QVBoxLayout(self)
        self.status = QLabel("…")
        self.connect_btn = QPushButton("Verbinden")
        self.disconnect_btn = QPushButton("Trennen")
        self.log_btn = QPushButton("Log anzeigen")
        self.settings_btn = QPushButton("Neu einrichten…")
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self._disconnect)
        self.log_btn.clicked.connect(self._show_log)
        self.settings_btn.clicked.connect(lambda: self._on_settings())
        for w in (self.status, self.connect_btn, self.disconnect_btn,
                  self.log_btn, self.settings_btn):
            layout.addWidget(w)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def refresh(self):
        up = is_vpn_up()
        if up:
            self._connecting = 0
            self.status.setText("Status: Verbunden")
        elif self._connecting > 0:
            self._connecting -= 1
            if self._connecting == 0:
                self.status.setText(
                    "Status: Verbindung fehlgeschlagen — „Log anzeigen“ für Details")
            else:
                self.status.setText("Status: Verbinde …")
        else:
            self.status.setText("Status: Getrennt")
        # Connect only when idle+down; disconnect while up or mid-attempt.
        self.connect_btn.setEnabled(not up and self._connecting == 0)
        self.disconnect_btn.setEnabled(up or self._connecting > 0)

    def _connect(self):
        try:
            tw.end(tw.TASK_UP)   # clear any stale blocking instance first
            tw.run(tw.TASK_UP)
            self._connecting = _CONNECT_TIMEOUT_TICKS
            self.status.setText("Status: Verbinde …")
        except Exception as exc:
            self._connecting = 0
            QMessageBox.critical(self, "Fehler", str(exc))
        self.refresh()

    def _disconnect(self):
        try:
            tw.run(tw.TASK_DOWN)
            tw.end(tw.TASK_UP)   # stop the lingering up-loop so reconnect works
            self._connecting = 0
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
        self.refresh()

    def _show_log(self):
        path = connect_log_path(str(cfgmod.config_path()))
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = "Noch kein Verbindungs-Log vorhanden."
        dlg = QDialog(self)
        dlg.setWindowTitle("Verbindungs-Log")
        dlg.resize(720, 480)
        v = QVBoxLayout(dlg)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        v.addWidget(view)
        dlg.exec()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("automatic VPN")
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.addWidget(self.stack)
        self.setup = SetupView(on_done=self._show_control)
        self.control = ControlView(on_settings=self._show_setup)
        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.control)
        self._route()

    def _route(self):
        view = gl.choose_view(cfgmod.load_config(), tw.is_registered())
        self.stack.setCurrentWidget(self.setup if view == "setup" else self.control)

    def _show_control(self):
        self.control.refresh()
        self.stack.setCurrentWidget(self.control)

    def _show_setup(self):
        self.stack.setCurrentWidget(self.setup)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.setMinimumSize(620, 520)
    win.resize(720, 560)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
