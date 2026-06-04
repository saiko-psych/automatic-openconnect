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
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QStackedWidget, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from . import config as cfgmod
from . import gui_logic as gl
from . import i18n
from .i18n import t
from . import preflight
from . import qr
from . import session
from . import tasks_windows as tw
from ._windows import is_vpn_up, connect_log_path
from .secrets import set_uni_login_password, set_uni_totp_secret

# How many 2-second status polls to wait for the tunnel before declaring
# the connect attempt failed. Must exceed the backend's worst case (auth +
# tunnel + orphaned-adapter cleanup can take ~60 s), so the GUI doesn't
# give up while the connection is actually still succeeding. ~70 s.
_CONNECT_TIMEOUT_TICKS = 35

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

def _wrap(layout) -> QWidget:
    """Wrap a layout in a QWidget (for QFormLayout.addRow)."""
    w = QWidget()
    w.setLayout(layout)
    return w


_FIX_LABELS = {
    "open_download": "fixbtn.open_download",
    "install_sso": "fixbtn.install_sso",
    "create_config": "fixbtn.create_config",
    "open_setup": "fixbtn.open_setup",
}


class PreflightDialog(QDialog):
    """Prerequisites checklist with one-click fixes where possible."""

    def __init__(self, parent, email, oc_path, sso_path, on_setup=None):
        super().__init__(parent)
        self._email, self._oc, self._sso = email, oc_path, sso_path
        self._on_setup = on_setup
        self._proc = None
        self.setWindowTitle(t("preflight.title"))
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
        foot = QLabel(t("preflight.all_ok") if preflight.all_ok(checks)
                      else t("preflight.todo"))
        foot.setObjectName("subheader")
        self._root.addWidget(foot)
        self._root.addStretch(1)

    def _row(self, c) -> QFrame:
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 4, 0, 4)
        mark = t("preflight.ok") if c.ok else t("preflight.missing")
        head = QLabel(f"[{mark}]  {t(c.name)}")
        head.setStyleSheet(
            "font-weight:600; color:%s;" % ("#3ba55d" if c.ok else "#e0a23c"))
        v.addWidget(head)
        if not c.ok:
            if c.fix:
                fix = QLabel(t(c.fix))
                fix.setWordWrap(True)
                fix.setObjectName("subheader")
                v.addWidget(fix)
            if c.action in _FIX_LABELS:
                btn = QPushButton(t(_FIX_LABELS[c.action]))
                btn.clicked.connect(lambda _, a=c.action, b=None: self._do(a))
                v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return frame

    def _do(self, action: str):
        if action == "open_download":
            webbrowser.open(preflight.OPENCONNECT_GUI_RELEASES)
        elif action == "create_config":
            try:
                p = preflight.create_config_toml()
                QMessageBox.information(self, t("config.created_title"),
                                        f"{t('config.created_msg')}\n{p}")
            except OSError as exc:
                QMessageBox.critical(self, t("generic.error"), str(exc))
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
        self._root.addWidget(QLabel(t("sso.installing")))
        self._proc.start(cmd[0], cmd[1:])
        if not self._proc.waitForStarted(5000):
            QMessageBox.critical(self, t("generic.error"), t("sso.no_uv"))
            self._proc = None
            self._rebuild()

    def _sso_done(self, code, _status):
        ok = (code == 0)
        self._proc = None
        QMessageBox.information(
            self, t("sso.install_title"),
            t("sso.install_ok") if ok else t("sso.install_fail") % code)
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
        self.stop_cisco = QCheckBox(t("setup.stop_cisco"))
        self.stop_cisco.setChecked(existing.get("stop_cisco_during_run", True))
        self.stop_mullvad = QCheckBox(t("setup.stop_mullvad"))
        self.stop_mullvad.setChecked(existing.get("stop_mullvad_during_run", True))

        form.addRow(t("setup.email"), self.email)
        form.addRow(t("setup.server"), self.server)
        form.addRow("openconnect.exe", self.oc)
        form.addRow("openconnect-sso", self.sso)
        self.pw.setPlaceholderText(t("setup.pw_ph"))
        self.totp.setPlaceholderText(t("setup.totp_ph"))
        form.addRow(t("setup.password"), self.pw)
        form.addRow(t("setup.totp"), self.totp)

        totp_help = QHBoxLayout()
        qr_btn = QPushButton(t("setup.load_qr"))
        qr_btn.setObjectName("ghost")
        qr_btn.clicked.connect(self._load_qr)
        help_btn = QPushButton(t("setup.totp_help_btn"))
        help_btn.setObjectName("ghost")
        help_btn.clicked.connect(self._show_totp_help)
        totp_help.addWidget(qr_btn)
        totp_help.addWidget(help_btn)
        form.addRow("", _wrap(totp_help))

        form.addRow(self.stop_cisco)
        form.addRow(self.stop_mullvad)

        check_btn = QPushButton(t("btn.check_prereqs"))
        check_btn.setObjectName("ghost")
        check_btn.clicked.connect(self._check_prereqs)
        form.addRow(check_btn)

        btn = QPushButton(t("setup.submit"))
        btn.setObjectName("primary")
        btn.clicked.connect(self._submit)
        form.addRow(btn)

    def _check_prereqs(self):
        show_preflight_dialog(self, self.email.text(),
                              self.oc.text(), self.sso.text())

    def _show_totp_help(self):
        QMessageBox.information(self, t("totp.help_title"), t("totp.help_text"))

    def _load_qr(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("qr.pick_title"), "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        try:
            secret = qr.secret_from_qr_image(path)
        except qr.QRUnavailable:
            QMessageBox.warning(self, t("qr.unavailable_title"),
                                t("qr.unavailable_msg"))
            return
        except Exception as exc:
            QMessageBox.critical(self, t("qr.read_error"), str(exc))
            return
        if secret:
            self.totp.setText(secret)
            QMessageBox.information(self, t("qr.found_title"), t("qr.found_msg"))
        else:
            QMessageBox.warning(self, t("qr.none_title"), t("qr.none_msg"))

    def _submit(self):
        fields = {
            "email": self.email.text(), "server": self.server.text(),
            "openconnect_path": self.oc.text(),
            "openconnect_sso_path": self.sso.text(),
        }
        errors = gl.validate_setup_form(fields)
        if errors:
            QMessageBox.warning(self, t("setup.fix_errors"),
                                "\n".join(t(e) for e in errors))
            return

        data = gl.build_auto_vpn_config(
            email=fields["email"], server=fields["server"],
            openconnect_path=fields["openconnect_path"],
            openconnect_sso_path=fields["openconnect_sso_path"],
            stop_cisco=self.stop_cisco.isChecked(),
            stop_mullvad=self.stop_mullvad.isChecked())
        path = cfgmod.save_config(data)

        try:
            tw.register(sys.executable, str(path),
                        frozen=getattr(sys, "frozen", False))
        except Exception as exc:  # VPNError or subprocess failure
            QMessageBox.critical(self, t("setup.failed"), str(exc))
            return

        # Commit credentials only once the elevated task actually exists.
        if self.pw.text():
            set_uni_login_password(fields["email"], self.pw.text())
        if self.totp.text():
            set_uni_totp_secret(fields["email"], self.totp.text().replace(" ", ""))

        QMessageBox.information(self, t("setup.done_title"), t("setup.done_msg"))
        self._on_done()


class ControlView(QWidget):
    def __init__(self, on_settings):
        super().__init__()
        self._on_settings = on_settings
        self._connecting = 0   # >0 while a connect attempt is in flight
        self._failed = False
        self.on_state = None   # MainWindow sets this to update the tray icon

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        header = QLabel("automatic VPN")
        header.setObjectName("header")
        sub = QLabel(t("app.subtitle"))
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

        self.connect_btn = QPushButton(t("btn.connect"))
        self.connect_btn.setObjectName("primary")
        self.disconnect_btn = QPushButton(t("btn.disconnect"))
        self.log_btn = QPushButton(t("btn.show_log"))
        self.log_btn.setObjectName("ghost")
        self.check_btn = QPushButton(t("btn.check_prereqs"))
        self.check_btn.setObjectName("ghost")
        self.settings_btn = QPushButton(t("btn.reconfigure"))
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
            self.status.setText(t("status.connected"))
        elif self._connecting > 0:
            self._connecting -= 1
            step = gl.connect_step_label(self._read_log())
            if step == "step.failed":
                self._connecting = 0
                self._failed = True
                self._set_dot(_DOT_RED)
                self.status.setText(t("status.failed_log"))
            elif self._connecting == 0:
                self._failed = True
                self._set_dot(_DOT_RED)
                self.status.setText(t("status.timeout_log"))
            else:
                self._set_dot(_DOT_AMBER)
                self.status.setText(t(step))
        elif self._failed:
            self._set_dot(_DOT_RED)
        else:
            self._set_dot(_DOT_GREY)
            self.status.setText(t("status.disconnected"))
        # Heartbeat: keep the watchdog's timestamp fresh while this GUI is
        # alive and owns a connection — including AFTER the display timeout
        # (self._failed). Otherwise a slow SAML login (auth can take far
        # longer than the display timeout) would stop the heartbeat, and the
        # up-task's watchdog would tear the tunnel down the moment it finally
        # comes up. Only a real GUI crash stops these writes.
        if up or self._connecting > 0 or self._failed:
            session.write_heartbeat(time.time(), background_ok=False)
        self.connect_btn.setEnabled(not up and self._connecting == 0)
        self.disconnect_btn.setEnabled(up or self._connecting > 0)
        if up:
            state = "connected"
        elif self._connecting > 0:
            state = "connecting"
        elif self._failed:
            state = "error"
        else:
            state = "disconnected"
        if self.on_state:
            self.on_state(state)

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
            self.status.setText(t("step.connecting"))
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
        except Exception as exc:
            self._connecting = 0
            QMessageBox.critical(self, t("generic.error"), str(exc))
            self.refresh()

    def _disconnect(self):
        try:
            tw.run(tw.TASK_DOWN)
            tw.end(tw.TASK_UP)   # stop the lingering up-loop so reconnect works
            session.clear()      # no active GUI-owned session anymore
            self._connecting = 0
            self._failed = False
        except Exception as exc:
            QMessageBox.critical(self, t("generic.error"), str(exc))
        self.refresh()

    def _show_log(self):
        path = connect_log_path(str(cfgmod.config_path()))
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            text = t("log.empty")
        dlg = QDialog(self)
        dlg.setWindowTitle(t("log.title"))
        dlg.resize(720, 480)
        v = QVBoxLayout(dlg)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        v.addWidget(view)
        dlg.exec()


class MainWindow(QWidget):
    def __init__(self, icon=None):
        super().__init__()
        self._icon = icon or QIcon()
        self.setWindowTitle("automatic VPN")
        outer = QVBoxLayout(self)

        # language selector (top bar, right-aligned)
        bar = QHBoxLayout()
        bar.addStretch(1)
        self.lang_label = QLabel(t("lang.label") + ":")
        bar.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        for code, label in i18n.LANGUAGES.items():
            self.lang_combo.addItem(label, code)
        self.lang_combo.setCurrentIndex(
            list(i18n.LANGUAGES).index(i18n.get_lang()))
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        bar.addWidget(self.lang_combo)
        outer.addLayout(bar)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.setup = SetupView(on_done=self._show_control)
        self.control = ControlView(on_settings=self._show_setup)
        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.control)
        self._build_tray()
        self.control.on_state = self._update_tray
        self._route()
        # Guided first setup: if we're on the setup screen and something is
        # missing, proactively open the checklist (with one-click fixes) so
        # the user is walked through the prerequisites.
        QTimer.singleShot(350, self._maybe_guide_first_setup)

    # --- system tray ----------------------------------------------------

    def _build_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._state_icons = {s: _state_icon(s)
                             for s in ("green", "amber", "blue", "red")}
        self.tray = QSystemTrayIcon(self._icon, self)
        self.tray.setToolTip("automatic VPN")
        menu = QMenu()
        self.act_open = menu.addAction(t("tray.open"))
        menu.addSeparator()
        self.act_connect = menu.addAction(t("btn.connect"))
        self.act_disconnect = menu.addAction(t("btn.disconnect"))
        menu.addSeparator()
        self.act_quit = menu.addAction(t("tray.quit"))
        self.tray.setContextMenu(menu)
        self.act_open.triggered.connect(self._show_window)
        self.act_connect.triggered.connect(lambda: self.control._connect())
        self.act_disconnect.triggered.connect(lambda: self.control._disconnect())
        self.act_quit.triggered.connect(self._quit)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # single left-click toggles the connection
            if is_vpn_up():
                self.control._disconnect()
            else:
                self.control._connect()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _update_tray(self, state):
        # state: connected | connecting | error | disconnected
        if self.tray is None:
            return
        name = {"connected": "green", "connecting": "amber",
                "error": "red", "disconnected": "blue"}.get(state, "blue")
        ic = self._state_icons.get(name)
        if ic is not None and not ic.isNull():
            self.tray.setIcon(ic)
        tip = {"connected": t("tray.tip_connected"),
               "connecting": t("tray.tip_connecting"),
               "error": t("tray.tip_error"),
               "disconnected": t("tray.tip_disconnected")}.get(state, "")
        self.tray.setToolTip(f"automatic VPN — {tip}")
        if hasattr(self, "act_connect"):
            self.act_connect.setEnabled(state in ("disconnected", "error"))
            self.act_disconnect.setEnabled(state in ("connected", "connecting"))

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self):
        if self._perform_exit_teardown():
            if self.tray is not None:
                self.tray.hide()
            QApplication.instance().quit()

    # --- language -------------------------------------------------------

    def _on_lang_changed(self, idx):
        code = self.lang_combo.itemData(idx)
        if not code or code == i18n.get_lang():
            return
        i18n.set_lang(code)
        data = cfgmod.load_config()
        data.setdefault("ui", {})["lang"] = code
        try:
            cfgmod.save_config(data)
        except OSError:
            pass
        self._apply_language()

    def _apply_language(self):
        """Re-create the views and re-label the tray so the new language
        takes effect immediately."""
        on_setup_view = self.stack.currentWidget() is self.setup
        self.control._timer.stop()   # stop the old poll before tearing it down
        self.stack.removeWidget(self.setup)
        self.stack.removeWidget(self.control)
        self.setup.deleteLater()
        self.control.deleteLater()
        self.setup = SetupView(on_done=self._show_control)
        self.control = ControlView(on_settings=self._show_setup)
        self.control.on_state = self._update_tray
        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.control)
        self.stack.setCurrentWidget(
            self.setup if on_setup_view else self.control)
        self.lang_label.setText(t("lang.label") + ":")
        if self.tray is not None:
            self.act_open.setText(t("tray.open"))
            self.act_connect.setText(t("btn.connect"))
            self.act_disconnect.setText(t("btn.disconnect"))
            self.act_quit.setText(t("tray.quit"))

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
        """The window's X minimises to the tray (the app keeps running and
        is controlled from the tray icon). Real exit is via the tray's
        'Beenden'. If there is no system tray, fall back to exit teardown."""
        if self.tray is not None:
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "automatic VPN", t("tray.minimized"),
                QSystemTrayIcon.MessageIcon.Information, 3000)
            return
        if self._perform_exit_teardown():
            event.accept()
        else:
            event.ignore()

    def _perform_exit_teardown(self) -> bool:
        """Handle the tunnel on real app exit: ask (disconnect / keep in
        background) honouring the saved preference. Returns False if the
        user cancelled (exit should be aborted)."""
        if not is_vpn_up():
            session.clear()
            return True
        data = cfgmod.load_config()
        ui = data.get("ui") or {}
        action = ui.get("close_action", "disconnect")
        if ui.get("ask_on_close", True):
            action = self._ask_close_action(data)
            if action == "cancel":
                return False
        self.control._timer.stop()
        if action == "background":
            session.write_heartbeat(time.time(), background_ok=True)
        else:  # disconnect
            try:
                tw.run(tw.TASK_DOWN)
                tw.end(tw.TASK_UP)
            except Exception:
                pass
            session.clear()
        return True

    def _ask_close_action(self, data: dict) -> str:
        """Show the close prompt. Returns 'disconnect' | 'background' |
        'cancel'. Persists the choice if 'don't ask again' is ticked."""
        box = QMessageBox(self)
        box.setWindowTitle(t("close.title"))
        box.setText(t("close.text"))
        box.setInformativeText(t("close.info"))
        disconnect_btn = box.addButton(t("close.disconnect"),
                                       QMessageBox.ButtonRole.AcceptRole)
        background_btn = box.addButton(t("close.background"),
                                       QMessageBox.ButtonRole.ActionRole)
        cancel_btn = box.addButton(t("close.cancel"),
                                   QMessageBox.ButtonRole.RejectRole)
        remember = QCheckBox(t("close.dont_ask"))
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


def _state_icon(name: str) -> QIcon:
    """Load a state-coloured tray icon (green/amber/blue/red)."""
    try:
        p = _ir.files("automatic_openconnect") / "assets" / f"icon-{name}.ico"
        return QIcon(str(p))
    except Exception:
        return QIcon()


def run() -> int:
    """Dual-mode entry for the frozen .exe (and `python -m`): if the first
    argument is a backend subcommand (up/down/status) run the CLI backend;
    otherwise launch the GUI. This lets one executable serve both the
    double-clickable app AND the elevated Scheduled Task (`automatic-vpn.exe
    up --config ...`)."""
    if sys.argv[1:2] and sys.argv[1] in ("up", "down", "status"):
        from ._windows import main_cli
        return main_cli()
    return main()


def main() -> int:
    # Pick up the saved UI language (default English) before building widgets.
    i18n.set_lang((cfgmod.load_config().get("ui") or {}).get("lang", "en"))
    app = QApplication(sys.argv)
    app.setStyleSheet(_STYLESHEET)
    # Keep the app alive when the window is closed — the tray icon controls
    # it. Real exit happens via the tray's "Beenden".
    app.setQuitOnLastWindowClosed(False)
    icon = _app_icon()
    app.setWindowIcon(icon)
    win = MainWindow(icon)
    win.setWindowIcon(icon)
    win.setMinimumSize(560, 520)
    win.resize(640, 560)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
