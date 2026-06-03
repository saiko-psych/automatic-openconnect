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

import importlib.resources as _ir
import time
import webbrowser

from PyQt6.QtCore import Qt, QProcess, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from . import config as cfgmod
from . import gui_logic as gl
from . import preflight
from . import session
from . import tasks_windows as tw
from ._windows import is_vpn_up, connect_log_path
from .secrets import set_uni_login_password, set_uni_totp_secret

# How many 3-second status polls to wait for the tunnel before declaring
# the connect attempt failed (~36 s — auth + tunnel usually take 10-25 s).
_CONNECT_TIMEOUT_TICKS = 12

# Status-dot colours per state.
_DOT_GREEN = "#3ba55d"   # connected
_DOT_AMBER = "#e0a23c"   # connecting
_DOT_RED = "#e04f4f"     # failed
_DOT_GREY = "#6b6e73"    # disconnected

_STYLESHEET = """
QWidget { background-color: #1e1f22; color: #e6e6e6;
          font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QLabel#header { font-size: 22px; font-weight: 600; color: #ffffff; }
QLabel#subheader { color: #9a9da3; font-size: 12px; }
QLabel#statusText { font-size: 16px; }
QLabel#dot { border-radius: 8px; min-width: 16px; max-width: 16px;
             min-height: 16px; max-height: 16px; }
QPushButton { background-color: #2b2d31; border: 1px solid #3a3d42;
              border-radius: 8px; padding: 11px 16px; }
QPushButton:hover { background-color: #34373c; }
QPushButton:disabled { color: #6b6e73; background-color: #232427;
                       border-color: #2c2e33; }
QPushButton#primary { background-color: #3b82f6; border: none;
                      color: #ffffff; font-weight: 600; font-size: 15px; }
QPushButton#primary:hover { background-color: #2f6fe0; }
QPushButton#primary:disabled { background-color: #2a3a55; color: #8aa0c0; }
QPushButton#ghost { background-color: transparent; color: #b8bbc0; }
QPushButton#ghost:hover { background-color: #2b2d31; }
QLineEdit { background-color: #2b2d31; border: 1px solid #3a3d42;
            border-radius: 6px; padding: 7px; }
QLineEdit:focus { border-color: #3b82f6; }
QPlainTextEdit { background-color: #141517; border: 1px solid #3a3d42;
                 font-family: 'Cascadia Mono', Consolas, monospace; }
QCheckBox { spacing: 8px; }
"""


_FIX_LABELS = {
    "open_download": "Download-Seite öffnen",
    "install_sso": "Jetzt installieren",
    "create_config": "config.toml anlegen",
    "open_setup": "Zum Setup",
}


class PreflightDialog(QDialog):
    """Prerequisites checklist with one-click fixes where possible."""

    def __init__(self, parent, email, oc_path, sso_path, on_setup=None):
        super().__init__(parent)
        self._email, self._oc, self._sso = email, oc_path, sso_path
        self._on_setup = on_setup
        self._proc = None
        self.setWindowTitle("Voraussetzungen")
        self.resize(720, 460)
        self._root = QVBoxLayout(self)
        self._rebuild()

    def _clear(self):
        while self._root.count():
            item = self._root.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _rebuild(self):
        self._clear()
        checks = preflight.check_all(self._email or None, self._oc, self._sso)
        for c in checks:
            self._root.addWidget(self._row(c))
        foot = QLabel("Alles bereit — du kannst dich verbinden."
                      if preflight.all_ok(checks)
                      else "Erledige die offenen Punkte — die Buttons helfen.")
        foot.setObjectName("subheader")
        self._root.addWidget(foot)
        self._root.addStretch(1)

    def _row(self, c) -> QFrame:
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 4, 0, 4)
        head = QLabel(f"[{'OK' if c.ok else 'FEHLT'}]  {c.name}")
        head.setStyleSheet(
            "font-weight:600; color:%s;" % ("#3ba55d" if c.ok else "#e0a23c"))
        v.addWidget(head)
        if not c.ok:
            if c.fix:
                fix = QLabel(c.fix)
                fix.setWordWrap(True)
                fix.setObjectName("subheader")
                v.addWidget(fix)
            if c.action in _FIX_LABELS:
                btn = QPushButton(_FIX_LABELS[c.action])
                btn.clicked.connect(lambda _, a=c.action, b=None: self._do(a))
                v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def _do(self, action: str):
        if action == "open_download":
            webbrowser.open(preflight.OPENCONNECT_GUI_RELEASES)
        elif action == "create_config":
            try:
                p = preflight.create_config_toml()
                QMessageBox.information(self, "Angelegt",
                                        f"config.toml angelegt:\n{p}")
            except OSError as exc:
                QMessageBox.critical(self, "Fehler", str(exc))
            self._rebuild()
        elif action == "install_sso":
            self._install_sso()
        elif action == "open_setup":
            if self._on_setup:
                self._on_setup()
            self.accept()

    def _install_sso(self):
        if self._proc is not None:
            return
        cmd = preflight.install_sso_command()
        self._proc = QProcess(self)
        self._proc.finished.connect(self._sso_done)
        self._clear()
        self._root.addWidget(QLabel("openconnect-sso wird installiert … "
                                    "(kann 1–2 Minuten dauern)"))
        self._proc.start(cmd[0], cmd[1:])
        if not self._proc.waitForStarted(5000):
            QMessageBox.critical(self, "Fehler",
                                 "uv nicht gefunden. Bitte uv installieren "
                                 "oder openconnect-sso manuell einrichten.")
            self._proc = None
            self._rebuild()

    def _sso_done(self, code, _status):
        ok = (code == 0)
        self._proc = None
        QMessageBox.information(
            self, "Installation",
            "openconnect-sso wurde installiert."
            if ok else "Installation fehlgeschlagen (Exit %s)." % code)
        self._rebuild()


def show_preflight_dialog(parent, email: str, oc_path: str, sso_path: str,
                          on_setup=None) -> None:
    PreflightDialog(parent, email, oc_path, sso_path, on_setup).exec()


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

        check_btn = QPushButton("Voraussetzungen prüfen")
        check_btn.setObjectName("ghost")
        check_btn.clicked.connect(self._check_prereqs)
        form.addRow(check_btn)

        btn = QPushButton("Einrichten (einmaliger Admin-Dialog)")
        btn.setObjectName("primary")
        btn.clicked.connect(self._submit)
        form.addRow(btn)

    def _check_prereqs(self):
        show_preflight_dialog(self, self.email.text(),
                              self.oc.text(), self.sso.text())

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
        self._failed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        header = QLabel("automatic VPN")
        header.setObjectName("header")
        sub = QLabel("Uni-Graz VPN — verbinden ohne Passwort & 2FA")
        sub.setObjectName("subheader")
        root.addWidget(header)
        root.addWidget(sub)
        root.addStretch(2)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.dot = QLabel()
        self.dot.setObjectName("dot")
        self.status = QLabel("…")
        self.status.setObjectName("statusText")
        row.addWidget(self.dot)
        row.addWidget(self.status)
        row.addStretch(1)
        root.addLayout(row)
        root.addStretch(3)

        self.connect_btn = QPushButton("Verbinden")
        self.connect_btn.setObjectName("primary")
        self.disconnect_btn = QPushButton("Trennen")
        self.log_btn = QPushButton("Log anzeigen")
        self.log_btn.setObjectName("ghost")
        self.check_btn = QPushButton("Voraussetzungen prüfen")
        self.check_btn.setObjectName("ghost")
        self.settings_btn = QPushButton("Neu einrichten…")
        self.settings_btn.setObjectName("ghost")
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self._disconnect)
        self.log_btn.clicked.connect(self._show_log)
        self.check_btn.clicked.connect(self._check_prereqs)
        self.settings_btn.clicked.connect(lambda: self._on_settings())
        for w in (self.connect_btn, self.disconnect_btn, self.log_btn,
                  self.check_btn, self.settings_btn):
            root.addWidget(w)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        self.refresh()

    def _check_prereqs(self):
        av = (cfgmod.load_config().get("auto_vpn") or {})
        show_preflight_dialog(self, av.get("user_email", ""),
                              av.get("openconnect_path", ""),
                              av.get("openconnect_sso_path", ""),
                              on_setup=self._on_settings)

    def _set_dot(self, color: str) -> None:
        self.dot.setStyleSheet(f"background-color: {color};")

    def _read_log(self) -> str:
        try:
            with open(connect_log_path(str(cfgmod.config_path())),
                      encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    def refresh(self):
        up = is_vpn_up()
        if up:
            self._connecting = 0
            self._failed = False
            self._set_dot(_DOT_GREEN)
            self.status.setText("Verbunden")
        elif self._connecting > 0:
            self._connecting -= 1
            step = gl.connect_step_label(self._read_log())
            if step == "Verbindung fehlgeschlagen":
                self._connecting = 0
                self._failed = True
                self._set_dot(_DOT_RED)
                self.status.setText("Verbindung fehlgeschlagen — „Log anzeigen“")
            elif self._connecting == 0:
                self._failed = True
                self._set_dot(_DOT_RED)
                self.status.setText("Zeitüberschreitung — „Log anzeigen“")
            else:
                self._set_dot(_DOT_AMBER)
                self.status.setText(step)
        elif self._failed:
            self._set_dot(_DOT_RED)
        else:
            self._set_dot(_DOT_GREY)
            self.status.setText("Getrennt")
        # Heartbeat: while this GUI is alive and owns a (pending) connection,
        # keep the watchdog's timestamp fresh so it does NOT tear the tunnel
        # down. If the GUI crashes, these writes stop and the up-task tears
        # the tunnel down within ~15 s.
        if up or self._connecting > 0:
            session.write_heartbeat(time.time(), background_ok=False)
        self.connect_btn.setEnabled(not up and self._connecting == 0)
        self.disconnect_btn.setEnabled(up or self._connecting > 0)

    def _connect(self):
        # Proactive prerequisite check: rather than fire a doomed connect and
        # show a cryptic failure, detect what's missing first and show the
        # checklist with instructions.
        av = (cfgmod.load_config().get("auto_vpn") or {})
        checks = preflight.check_all(av.get("user_email") or None,
                                     av.get("openconnect_path", ""),
                                     av.get("openconnect_sso_path", ""))
        if not preflight.all_ok(checks):
            show_preflight_dialog(self, av.get("user_email", ""),
                                  av.get("openconnect_path", ""),
                                  av.get("openconnect_sso_path", ""),
                                  on_setup=self._on_settings)
            return
        try:
            # Fresh heartbeat BEFORE the task starts so the watchdog sees an
            # owning GUI from the first moment.
            session.write_heartbeat(time.time(), background_ok=False)
            tw.end(tw.TASK_UP)   # clear any stale blocking instance first
            tw.run(tw.TASK_UP)
            self._connecting = _CONNECT_TIMEOUT_TICKS
            self._failed = False
            self._set_dot(_DOT_AMBER)
            self.status.setText("Verbinde …")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        except Exception as exc:
            self._connecting = 0
            QMessageBox.critical(self, "Fehler", str(exc))
            self.refresh()

    def _disconnect(self):
        try:
            tw.run(tw.TASK_DOWN)
            tw.end(tw.TASK_UP)   # stop the lingering up-loop so reconnect works
            session.clear()      # no active GUI-owned session anymore
            self._connecting = 0
            self._failed = False
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
        # Guided first setup: if we're on the setup screen and something is
        # missing, proactively open the checklist (with one-click fixes) so
        # the user is walked through the prerequisites.
        QTimer.singleShot(350, self._maybe_guide_first_setup)

    def _route(self):
        view = gl.choose_view(cfgmod.load_config(), tw.is_registered())
        self.stack.setCurrentWidget(self.setup if view == "setup" else self.control)

    def _maybe_guide_first_setup(self):
        if self.stack.currentWidget() is not self.setup:
            return
        av = (cfgmod.load_config().get("auto_vpn") or {})
        checks = preflight.check_all(av.get("user_email") or None,
                                     av.get("openconnect_path", ""),
                                     av.get("openconnect_sso_path", ""))
        if not preflight.all_ok(checks):
            show_preflight_dialog(self, av.get("user_email", ""),
                                  av.get("openconnect_path", ""),
                                  av.get("openconnect_sso_path", ""),
                                  on_setup=self._show_setup)

    def _show_control(self):
        self.control.refresh()
        self.stack.setCurrentWidget(self.control)

    def _show_setup(self):
        self.stack.setCurrentWidget(self.setup)

    # --- close behaviour ------------------------------------------------

    def closeEvent(self, event):
        """When closing while connected: ask whether to disconnect or keep
        the tunnel running in the background (with a 'don't ask again'
        option). Stop the status timer first so it can't overwrite the
        final heartbeat we write here."""
        if not is_vpn_up():
            session.clear()
            event.accept()
            return

        data = cfgmod.load_config()
        ui = data.get("ui") or {}
        action = ui.get("close_action", "disconnect")
        if ui.get("ask_on_close", True):
            action = self._ask_close_action(data)
            if action == "cancel":
                event.ignore()
                return

        self.control._timer.stop()
        if action == "background":
            # Tell the watchdog to leave the tunnel alone.
            session.write_heartbeat(time.time(), background_ok=True)
        else:  # disconnect
            try:
                tw.run(tw.TASK_DOWN)
                tw.end(tw.TASK_UP)
            except Exception:
                pass
            session.clear()
        event.accept()

    def _ask_close_action(self, data: dict) -> str:
        """Show the close prompt. Returns 'disconnect' | 'background' |
        'cancel'. Persists the choice if 'don't ask again' is ticked."""
        box = QMessageBox(self)
        box.setWindowTitle("automatic VPN")
        box.setText("Der VPN-Tunnel ist noch verbunden.")
        box.setInformativeText("Möchtest du die Verbindung trennen oder im "
                               "Hintergrund weiterlaufen lassen?")
        disconnect_btn = box.addButton("Trennen",
                                       QMessageBox.ButtonRole.AcceptRole)
        background_btn = box.addButton("Im Hintergrund lassen",
                                       QMessageBox.ButtonRole.ActionRole)
        cancel_btn = box.addButton("Abbrechen",
                                   QMessageBox.ButtonRole.RejectRole)
        remember = QCheckBox("Diese Abfrage nicht mehr anzeigen")
        box.setCheckBox(remember)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_btn or clicked is None:
            return "cancel"
        action = "background" if clicked is background_btn else "disconnect"
        if remember.isChecked():
            data.setdefault("ui", {})
            data["ui"]["ask_on_close"] = False
            data["ui"]["close_action"] = action
            try:
                cfgmod.save_config(data)
            except OSError:
                pass
        return action


def _app_icon() -> QIcon:
    """Load the bundled app icon; empty QIcon if it cannot be found."""
    try:
        p = _ir.files("automatic_openconnect") / "assets" / "icon.ico"
        return QIcon(str(p))
    except Exception:
        return QIcon()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(_STYLESHEET)
    icon = _app_icon()
    app.setWindowIcon(icon)
    win = MainWindow()
    win.setWindowIcon(icon)
    win.setMinimumSize(560, 520)
    win.resize(640, 560)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
