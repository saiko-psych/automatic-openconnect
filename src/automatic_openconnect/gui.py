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
    QApplication, QCheckBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from . import config as cfgmod
from . import gui_logic as gl
from . import tasks_windows as tw
from ._windows import is_vpn_up
from .secrets import set_uni_login_password, set_uni_totp_secret


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
        layout = QVBoxLayout(self)
        self.status = QLabel("…")
        self.connect_btn = QPushButton("Verbinden")
        self.disconnect_btn = QPushButton("Trennen")
        self.settings_btn = QPushButton("Neu einrichten…")
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self._disconnect)
        self.settings_btn.clicked.connect(lambda: self._on_settings())
        for w in (self.status, self.connect_btn, self.disconnect_btn,
                  self.settings_btn):
            layout.addWidget(w)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def refresh(self):
        up = is_vpn_up()
        self.status.setText("🟢 Verbunden" if up else "⚪ Getrennt")
        self.connect_btn.setEnabled(not up)
        self.disconnect_btn.setEnabled(up)

    def _connect(self):
        try:
            tw.end(tw.TASK_UP)   # clear any stale blocking instance first
            tw.run(tw.TASK_UP)
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
        self.refresh()

    def _disconnect(self):
        try:
            tw.run(tw.TASK_DOWN)
            tw.end(tw.TASK_UP)   # stop the lingering up-loop so reconnect works
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
        self.refresh()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Uni Graz VPN")
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
