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
import os
import time
import webbrowser

from PyQt6.QtCore import Qt, QProcess, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import config as cfgmod
from . import gui_logic as gl
from . import i18n
from .i18n import t
from . import preflight
from . import qr
from . import autostart
from . import session
from . import tasks_windows as tw
from . import totp_hotkey
from ._windows import is_vpn_up, connect_log_path
from .secrets import (get_uni_login_password, get_uni_totp_secret,
                      set_uni_login_password, set_uni_totp_secret)

# How many 2-second status polls to wait for the tunnel before declaring
# the connect attempt failed. Must exceed the backend's worst case (auth +
# tunnel + orphaned-adapter cleanup can take ~60 s), so the GUI doesn't
# give up while the connection is actually still succeeding. ~70 s.
_CONNECT_TIMEOUT_TICKS = 35

_REPO_URL = "https://github.com/saiko-psych/automatic-openconnect"
# Where the in-app "Report a bug" button sends the user. The chooser lets
# them pick the bug-report vs feature-request issue template.
_ISSUE_URL = _REPO_URL + "/issues/new/choose"

# Per-state colours for the status dot AND the tray icon. User-overridable
# in Settings (ui.state_colors); these are the defaults.
_DEFAULT_STATE_COLORS = {
    "connected": "#3ba55d",     # green
    "connecting": "#e0a23c",    # amber
    "disconnected": "#3b82f6",  # blue
    "error": "#e04f4f",         # red
}


def _state_color(state: str) -> str:
    override = (cfgmod.load_config().get("ui") or {}).get("state_colors") or {}
    return override.get(state) or _DEFAULT_STATE_COLORS.get(state, "#6b6e73")

# Accent presets: (base, hover). Picked in Settings; recolours the primary
# button, focus ring AND the action icons. Status-dot colours stay semantic.
_ACCENTS = {
    "blue":   ("#3b82f6", "#2f6fe0"),
    "green":  ("#3ba55d", "#2f8b4d"),
    "purple": ("#8b5cf6", "#7a4ee0"),
    "orange": ("#e0822f", "#c86f22"),
    "teal":   ("#14b8a6", "#0fa192"),
    "pink":   ("#ec4899", "#d63a86"),
}
DEFAULT_ACCENT = "blue"

# Light / dark palettes. Every colour the stylesheet needs comes from here so
# a theme is just a swap of this dict.
_PALETTES = {
    "dark": {
        "BG": "#1e1f22", "FG": "#e6e6e6", "SUB": "#9a9da3", "HEADER": "#ffffff",
        "PANEL": "#2b2d31", "BORDER": "#3a3d42", "HOVER": "#34373c",
        "DISFG": "#6b6e73", "DISBG": "#232427", "INDBORDER": "#5a5d63",
        "POPUPSEL": "#3a3d42", "LOGBG": "#141517",
    },
    "light": {
        "BG": "#f4f5f7", "FG": "#1c1d20", "SUB": "#5c5f66", "HEADER": "#101114",
        "PANEL": "#ffffff", "BORDER": "#cdd0d6", "HOVER": "#e8eaed",
        "DISFG": "#a3a6ac", "DISBG": "#e9eaec", "INDBORDER": "#aab0b8",
        "POPUPSEL": "#dfe2e7", "LOGBG": "#ffffff",
    },
}
DEFAULT_THEME = "dark"

# Current accent — used to tint action icons (the stylesheet handles the rest).
_CURRENT_ACCENT = DEFAULT_ACCENT

_STYLESHEET_TMPL = """
QWidget { background-color: @BG@; color: @FG@;
          font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QLabel#header { font-size: 22px; font-weight: 600; color: @HEADER@; }
QLabel#subheader { color: @SUB@; font-size: 12px; }
QLabel#sectionTitle { color: @HEADER@; font-weight: 600; font-size: 14px; }
QLabel#statusText { font-size: 16px; }
QLabel#dot { border-radius: 8px; min-width: 16px; max-width: 16px;
             min-height: 16px; max-height: 16px; }
QPushButton { background-color: @PANEL@; border: 1px solid @BORDER@;
              border-radius: 8px; padding: 11px 16px; }
QPushButton:hover { background-color: @HOVER@; }
QPushButton:disabled { color: @DISFG@; background-color: @DISBG@;
                       border-color: @BORDER@; }
QPushButton#primary { background-color: @ACCENT@; border: none;
                      color: #ffffff; font-weight: 600; font-size: 15px; }
QPushButton#primary:hover { background-color: @ACCENT_HOVER@; }
QPushButton#primary:disabled { background-color: @DISBG@; color: @DISFG@; }
QPushButton#ghost { background-color: transparent; color: @FG@; }
QPushButton#ghost:hover { background-color: @HOVER@; }
QLineEdit { background-color: @PANEL@; border: 1px solid @BORDER@;
            border-radius: 6px; padding: 7px; selection-background-color: @ACCENT@; }
QLineEdit:focus { border-color: @ACCENT@; }
QComboBox { background-color: @PANEL@; border: 1px solid @BORDER@;
            border-radius: 6px; padding: 5px 10px; }
QComboBox:focus { border-color: @ACCENT@; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right;
                       width: 24px; border: none; }
QComboBox::down-arrow { image: url("@CHEVRON@"); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background-color: @PANEL@; color: @FG@;
                              border: 1px solid @BORDER@;
                              selection-background-color: @POPUPSEL@; outline: none; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid @INDBORDER@;
                       border-radius: 4px; background: @PANEL@; }
QCheckBox::indicator:hover { border-color: @ACCENT@; }
QCheckBox::indicator:checked { background: @ACCENT@; border-color: @ACCENT@;
                               image: url("@CHECK@"); }
QProgressBar { background-color: @PANEL@; border: 1px solid @BORDER@;
               border-radius: 7px; height: 14px; }
QProgressBar::chunk { background-color: @ACCENT@; border-radius: 7px; }
QPlainTextEdit { background-color: @LOGBG@; color: @FG@; border: 1px solid @BORDER@;
                 font-family: 'Cascadia Mono', Consolas, monospace; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: @BORDER@; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background-color: @PANEL@; color: @FG@; border: 1px solid @BORDER@; }
"""


def _asset_url(name: str) -> str:
    """Forward-slash absolute path to a bundled PNG, for QSS url()."""
    try:
        return str(_ir.files("automatic_openconnect") / "assets"
                   / f"{name}.png").replace("\\", "/")
    except Exception:
        return ""


def _build_stylesheet(accent: str = DEFAULT_ACCENT,
                      theme: str = DEFAULT_THEME) -> str:
    pal = _PALETTES.get(theme, _PALETTES[DEFAULT_THEME])
    base, hover = _ACCENTS.get(accent, _ACCENTS[DEFAULT_ACCENT])
    s = _STYLESHEET_TMPL
    for key, value in pal.items():
        s = s.replace(f"@{key}@", value)
    s = s.replace("@ACCENT_HOVER@", hover).replace("@ACCENT@", base)
    s = s.replace("@CHEVRON@", _asset_url("chevron"))
    s = s.replace("@CHECK@", _asset_url("check"))
    return s


def _wrap(layout) -> QWidget:
    """Wrap a layout in a QWidget (for QFormLayout.addRow)."""
    w = QWidget()
    w.setLayout(layout)
    return w


def _png_icon(name: str) -> QIcon:
    """Load a bundled PNG asset as a QIcon (untinted)."""
    try:
        p = _ir.files("automatic_openconnect") / "assets" / f"{name}.png"
        return QIcon(str(p))
    except Exception:
        return QIcon()


def _accent_icon(name: str) -> QIcon:
    """Bundled monochrome PNG recoloured to the current accent, so the action
    icons match the theme (and stay visible in both light and dark mode)."""
    from PyQt6.QtGui import QColor, QPainter, QPixmap
    base = _ACCENTS.get(_CURRENT_ACCENT, _ACCENTS[DEFAULT_ACCENT])[0]
    try:
        p = _ir.files("automatic_openconnect") / "assets" / f"{name}.png"
        pix = QPixmap(str(p))
        if pix.isNull():
            return QIcon()
        out = QPixmap(pix.size())
        out.fill(Qt.GlobalColor.transparent)
        painter = QPainter(out)
        painter.drawPixmap(0, 0, pix)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(out.rect(), QColor(base))
        painter.end()
        return QIcon(out)
    except Exception:
        return QIcon()


def _add_reveal_eye(line_edit: QLineEdit) -> None:
    """Mask the field and add an eye icon *inside* it (trailing action)
    that toggles between hidden and revealed."""
    line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    act = line_edit.addAction(_accent_icon("eye"),
                              QLineEdit.ActionPosition.TrailingPosition)
    act.setToolTip(t("btn.show"))
    shown = {"on": False}

    def _toggle() -> None:
        shown["on"] = not shown["on"]
        line_edit.setEchoMode(QLineEdit.EchoMode.Normal if shown["on"]
                              else QLineEdit.EchoMode.Password)
        act.setIcon(_accent_icon("eye-off" if shown["on"] else "eye"))
        act.setToolTip(t("btn.hide") if shown["on"] else t("btn.show"))

    act.triggered.connect(_toggle)


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
        # Real-time tracking: while the checklist is open, re-check the
        # prerequisites every few seconds so it reflects reality live (e.g.
        # after you install a tool or create the config in another window).
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._tick)
        self._poll.start(2500)

    def _tick(self):
        if self._proc is None:   # don't clobber an in-progress install view
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
        close_btn = QPushButton(t("preflight.close"))
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.accept)
        self._root.addWidget(close_btn)

    def _row(self, c) -> QFrame:
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 4, 0, 4)
        if c.ok:
            mark, color = t("preflight.ok"), "#3ba55d"
        elif c.warn_only:
            mark, color = t("preflight.warn"), "#e0a23c"
        else:
            mark, color = t("preflight.missing"), "#e04f4f"
        head = QLabel(f"[{mark}]  {t(c.name)}")
        head.setStyleSheet(f"font-weight:600; color:{color};")
        v.addWidget(head)
        if not c.ok:
            if c.fix:
                fix = QLabel(t(c.fix))
                fix.setWordWrap(True)
                fix.setObjectName("subheader")
                v.addWidget(fix)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            if c.action in _FIX_LABELS:
                btn = QPushButton(t(_FIX_LABELS[c.action]))
                btn.clicked.connect(lambda _, a=c.action, b=None: self._do(a))
                row.addWidget(btn)
            # For openconnect.exe also offer a direct "Locate…" — covers any
            # non-standard install location that auto-detection missed.
            if c.name == "check.openconnect":
                locate = QPushButton(t("preflight.locate"))
                locate.setObjectName("ghost")
                locate.clicked.connect(self._locate_openconnect)
                row.addWidget(locate)
            row.addStretch(1)
            v.addLayout(row)
        return frame

    def _do(self, action: str):
        if action == "open_download":
            webbrowser.open(preflight.OPENCONNECT_GUI_RELEASES)
        elif action == "create_config":
            slot = int((cfgmod.load_config().get("auto_vpn") or {})
                       .get("totp_token_slot", 0) or 0)
            try:
                p = preflight.create_config_toml(slot)
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

    def _locate_openconnect(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("preflight.locate"), "",
            "openconnect.exe (openconnect.exe);;Programs (*.exe);;All files (*)")
        if not path:
            return
        path = gl.normalize_openconnect_path(path)  # gui.exe → openconnect.exe
        # Persist so setup and the backend use it, then re-check live.
        self._oc = path
        data = cfgmod.load_config()
        data.setdefault("auto_vpn", {})["openconnect_path"] = path
        try:
            cfgmod.save_config(data)
        except OSError:
            pass
        self._rebuild()

    def _install_sso(self):
        if self._proc is not None:
            return
        cmd = preflight.install_sso_command()
        if not cmd:
            # uv not found anywhere — offer to install it (official installer,
            # no admin and no Python required).
            ans = QMessageBox.question(
                self, t("sso.uv_title"), t("sso.uv_msg"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans == QMessageBox.StandardButton.Yes:
                self._install_uv()
            return
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels)
        self._proc.finished.connect(self._sso_done)
        self._show_busy(t("sso.installing"))
        self._proc.start(cmd[0], cmd[1:])
        if not self._proc.waitForStarted(8000):
            QMessageBox.critical(self, t("generic.error"), t("sso.no_uv"))
            self._proc = None
            self._rebuild()

    def _install_uv(self):
        if self._proc is not None:
            return
        self._proc = QProcess(self)
        self._proc.finished.connect(self._uv_done)
        self._show_busy(t("sso.installing_uv"))
        self._proc.start("powershell", [
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            "irm https://astral.sh/uv/install.ps1 | iex"])
        if not self._proc.waitForStarted(8000):
            QMessageBox.critical(self, t("generic.error"), t("sso.uv_fail"))
            self._proc = None
            self._rebuild()

    def _show_busy(self, message: str) -> None:
        """Centered message + an indeterminate progress bar, while a
        background install runs (uv / openconnect-sso)."""
        self._clear()
        self._root.addStretch(1)
        lbl = QLabel(message)
        lbl.setObjectName("statusText")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(lbl)
        bar = QProgressBar()
        bar.setRange(0, 0)            # indeterminate (marquee)
        bar.setTextVisible(False)
        bar.setFixedWidth(360)
        self._root.addWidget(bar, alignment=Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(t("sso.installing_hint"))
        hint.setObjectName("subheader")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.addWidget(hint)
        self._root.addStretch(1)

    def _uv_done(self, code, _status):
        self._proc = None
        if code == 0 and preflight.install_sso_command():
            self._install_sso()   # uv is here now → continue with the login helper
        else:
            QMessageBox.warning(self, t("sso.uv_title"), t("sso.uv_fail"))
            self._rebuild()

    def _sso_done(self, code, _status):
        out = ""
        if self._proc is not None:
            try:
                out = bytes(self._proc.readAllStandardOutput()).decode(
                    "utf-8", "replace")
            except Exception:
                out = ""
        self._proc = None
        if code == 0:
            QMessageBox.information(self, t("sso.install_title"),
                                    t("sso.install_ok"))
        else:
            box = QMessageBox(self)
            box.setWindowTitle(t("sso.install_title"))
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(t("sso.install_fail") % code)
            if out.strip():
                box.setDetailedText(out[-4000:])  # expandable "Details"
            box.exec()
        self._rebuild()


def show_preflight_dialog(parent, email: str, oc_path: str, sso_path: str,
                          on_setup=None) -> None:
    PreflightDialog(parent, email, oc_path, sso_path, on_setup).exec()


class SetupView(QWidget):
    def __init__(self, on_done, on_cancel=None):
        super().__init__()
        self._on_done = on_done
        self._on_cancel = on_cancel
        # Already set up? Then this view acts as a config editor: it offers a
        # Back button and saves without re-registering (no second UAC prompt).
        self._configured = (cfgmod.is_configured(cfgmod.load_config())
                            and tw.is_registered())

        # Scroll the form so nothing ever clips on a short window.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        form = QFormLayout(body)
        form.setContentsMargins(28, 22, 28, 22)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        existing = (cfgmod.load_config().get("auto_vpn") or {})
        self.email = QLineEdit(existing.get("user_email", ""))
        self.server = QLineEdit(existing.get("server", "univpn.uni-graz.at"))
        self.oc = QLineEdit(gl.normalize_openconnect_path(
            existing.get("openconnect_path", "")))
        self.sso = QLineEdit(existing.get("openconnect_sso_path") or gl.detect_openconnect_sso())

        # The setup form doubles as the config view: prefill the currently
        # stored credentials (masked) so they can be revealed via the eye.
        email = existing.get("user_email", "")
        try:
            cur_pw = (get_uni_login_password(email) or "") if email else ""
            cur_seed = (get_uni_totp_secret(email) or "") if email else ""
        except Exception:
            cur_pw = cur_seed = ""
        self.pw = QLineEdit(cur_pw)
        self.pw.setPlaceholderText(t("setup.pw_ph"))
        _add_reveal_eye(self.pw)
        self.totp = QLineEdit(cur_seed)
        self.totp.setPlaceholderText(t("setup.totp_ph"))
        _add_reveal_eye(self.totp)

        from ._windows import DEFAULT_CONFLICTING_SERVICES
        services = (existing.get("conflicting_services")
                    or list(DEFAULT_CONFLICTING_SERVICES))
        self.stop_conflicting = QCheckBox(t("setup.stop_conflicting"))
        self.stop_conflicting.setChecked(
            existing.get("stop_conflicting_services", True))
        self.services = QLineEdit(", ".join(services))
        self.services.setPlaceholderText(t("setup.services_ph"))

        # Show the START of long values (paths/seed), not the scrolled end.
        for le in (self.email, self.server, self.oc, self.sso,
                   self.totp, self.services):
            le.setCursorPosition(0)

        form.addRow(t("setup.email"), self.email)
        form.addRow(t("setup.server"), self.server)
        form.addRow("openconnect.exe", self._with_browse(self.oc))
        form.addRow("openconnect-sso", self._with_browse(self.sso))
        form.addRow(t("setup.password"), self.pw)
        form.addRow(t("setup.totp"), self.totp)

        totp_help = QHBoxLayout()
        totp_help.setContentsMargins(0, 0, 0, 0)
        qr_btn = QPushButton(t("setup.load_qr"))
        qr_btn.setObjectName("ghost")
        qr_btn.clicked.connect(self._load_qr)
        paste_btn = QPushButton(t("setup.paste_seed"))
        paste_btn.setObjectName("ghost")
        paste_btn.clicked.connect(self._paste_seed)
        help_btn = QPushButton(t("setup.totp_help_btn"))
        help_btn.setObjectName("ghost")
        help_btn.clicked.connect(self._show_totp_help)
        totp_help.addWidget(qr_btn)
        totp_help.addWidget(paste_btn)
        totp_help.addWidget(help_btn)
        totp_help.addStretch(1)
        form.addRow("", _wrap(totp_help))

        # Which 2FA token tile to pick when several are registered (Keycloak
        # shows one tile per token and validates against the selected one).
        self.token_slot = QComboBox()
        self.token_slot.addItem(t("setup.slot_default"), 0)
        for n in (1, 2, 3, 4):
            self.token_slot.addItem(str(n), n)
        cur_slot = int(existing.get("totp_token_slot", 0) or 0)
        self.token_slot.setCurrentIndex(cur_slot if 0 <= cur_slot <= 4 else 0)
        self.token_slot.setMaximumWidth(220)
        form.addRow(t("setup.token_slot"), self.token_slot)

        ui = (cfgmod.load_config().get("ui") or {})
        self.totp_hotkey_cb = QCheckBox(
            t("setup.totp_hotkey").format(combo=totp_hotkey.DEFAULT_HOTKEY_LABEL))
        self.totp_hotkey_cb.setChecked(ui.get("totp_hotkey", True))
        form.addRow(self.totp_hotkey_cb)

        form.addRow(self.stop_conflicting)
        form.addRow(t("setup.services"), self.services)

        check_btn = QPushButton(t("btn.check_prereqs"))
        check_btn.setObjectName("ghost")
        check_btn.clicked.connect(self._check_prereqs)
        form.addRow(check_btn)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        if self._on_cancel is not None and self._configured:
            back_btn = QPushButton(t("btn.back"))
            back_btn.setObjectName("ghost")
            back_btn.clicked.connect(lambda: self._on_cancel())
            buttons.addWidget(back_btn)
        submit = QPushButton(t("setup.save") if self._configured
                             else t("setup.submit"))
        submit.setObjectName("primary")
        submit.clicked.connect(self._submit)
        buttons.addWidget(submit, 1)
        form.addRow(_wrap(buttons))

    def _with_browse(self, line_edit: QLineEdit) -> QWidget:
        """Wrap a path field with a 'Browse…' button (works for any install
        location, so a non-standard openconnect path is always selectable)."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton(t("setup.browse"))
        btn.setObjectName("ghost")
        btn.setFixedWidth(96)
        btn.clicked.connect(lambda: self._browse(line_edit))
        row.addWidget(line_edit)
        row.addWidget(btn)
        return _wrap(row)

    def _browse(self, line_edit: QLineEdit) -> None:
        start = os.path.dirname(line_edit.text()) if line_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, t("setup.browse"), start,
            "Programs (*.exe);;All files (*)")
        if path:
            if line_edit is self.oc:
                path = gl.normalize_openconnect_path(path)  # gui.exe → cli
            line_edit.setText(path)
            line_edit.setCursorPosition(0)

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

    def _paste_seed(self):
        text, ok = QInputDialog.getMultiLineText(
            self, t("setup.paste_seed"), t("setup.paste_seed_prompt"), "")
        if not ok or not text.strip():
            return
        try:
            secret = qr.secret_from_text(text)
        except Exception as exc:  # noqa: BLE001 - surface as a friendly error
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
            "openconnect_path": gl.normalize_openconnect_path(self.oc.text()),
            "openconnect_sso_path": self.sso.text(),
        }
        errors = gl.validate_setup_form(fields)
        if errors:
            QMessageBox.warning(self, t("setup.fix_errors"),
                                "\n".join(t(e) for e in errors))
            return

        # Merge into the existing config so we never clobber the ui block
        # (language, close-on-exit preference) when reconfiguring.
        data = cfgmod.load_config()
        slot = int(self.token_slot.currentData() or 0)
        data["auto_vpn"] = gl.build_auto_vpn_config(
            email=fields["email"], server=fields["server"],
            openconnect_path=fields["openconnect_path"],
            openconnect_sso_path=fields["openconnect_sso_path"],
            stop_conflicting=self.stop_conflicting.isChecked(),
            conflicting_services=gl.parse_services(self.services.text()),
            totp_token_slot=slot)["auto_vpn"]
        data.setdefault("ui", {})["totp_hotkey"] = self.totp_hotkey_cb.isChecked()
        path = cfgmod.save_config(data)

        # Keep openconnect-sso's config.toml in sync with the chosen token
        # slot (regenerate it if a slot is set or the file already exists).
        try:
            if slot or os.path.exists(preflight.CONFIG_TOML):
                preflight.create_config_toml(slot)
        except OSError:
            pass

        # Register the elevated tasks only the first time (the one UAC prompt).
        # When already set up this view is just a config editor, so saving
        # must NOT trigger another admin prompt.
        already_registered = tw.is_registered()
        if not already_registered:
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

        QMessageBox.information(
            self, t("setup.done_title"),
            t("setup.saved_msg") if already_registered else t("setup.done_msg"))
        self._on_done()


class ControlView(QWidget):
    def __init__(self, on_settings, on_app_settings):
        super().__init__()
        self._on_settings = on_settings          # VPN configuration
        self._on_app_settings = on_app_settings   # app settings
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
        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self._disconnect)
        root.addWidget(self.connect_btn)
        root.addWidget(self.disconnect_btn)

        # Secondary actions in a tidy 2-column grid.
        self.log_btn = QPushButton(t("btn.show_log"))
        self.check_btn = QPushButton(t("btn.check_prereqs"))
        self.config_btn = QPushButton(t("btn.reconfigure"))
        self.app_settings_btn = QPushButton(t("settings.title"))
        self.app_settings_btn.setIcon(_accent_icon("gear"))
        self.bug_btn = QPushButton(t("btn.report_bug"))
        self.bug_btn.setIcon(_accent_icon("bug"))
        for b in (self.log_btn, self.check_btn, self.config_btn,
                  self.app_settings_btn, self.bug_btn):
            b.setObjectName("ghost")
        self.log_btn.clicked.connect(self._show_log)
        self.check_btn.clicked.connect(self._check_prereqs)
        self.config_btn.clicked.connect(lambda: self._on_settings())
        self.app_settings_btn.clicked.connect(lambda: self._on_app_settings())
        self.bug_btn.clicked.connect(self._report_bug)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(self.log_btn, 0, 0)
        grid.addWidget(self.check_btn, 0, 1)
        grid.addWidget(self.config_btn, 1, 0)
        grid.addWidget(self.app_settings_btn, 1, 1)
        grid.addWidget(self.bug_btn, 2, 0, 1, 2)
        root.addLayout(grid)

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

    def _report_bug(self):
        webbrowser.open(_ISSUE_URL)

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
            self._set_dot(_state_color("connected"))
            self.status.setText(t("status.connected"))
        elif self._connecting > 0:
            self._connecting -= 1
            step = gl.connect_step_label(self._read_log())
            if step == "step.failed":
                self._connecting = 0
                self._failed = True
                self._set_dot(_state_color("error"))
                self.status.setText(t("status.failed_log"))
            elif self._connecting == 0:
                self._failed = True
                self._set_dot(_state_color("error"))
                self.status.setText(t("status.timeout_log"))
            else:
                self._set_dot(_state_color("connecting"))
                self.status.setText(t(step))
        elif self._failed:
            self._set_dot(_state_color("error"))
        else:
            self._set_dot(_state_color("disconnected"))
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
            self._set_dot(_state_color("connecting"))
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


class SettingsView(QWidget):
    """App-level settings, kept separate from the VPN *configuration*:
    startup & tray behaviour, appearance, maintenance shortcuts, and the
    legal/about block. Every change applies and persists immediately."""

    def __init__(self, on_back, on_appearance_changed=None):
        super().__init__()
        self._on_back = on_back
        self._on_appearance_changed = on_appearance_changed

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(8)

        header = QLabel(t("settings.title"))
        header.setObjectName("header")
        root.addWidget(header)

        ui = (cfgmod.load_config().get("ui") or {})

        # --- Startup & tray -------------------------------------------
        root.addWidget(self._section(t("settings.sec_startup")))
        self.cb_autostart = QCheckBox(t("settings.autostart"))
        try:
            self.cb_autostart.setChecked(autostart.is_enabled())
        except Exception:
            self.cb_autostart.setEnabled(False)
        self.cb_autostart.toggled.connect(self._on_autostart)
        root.addWidget(self.cb_autostart)

        self.cb_minimized = QCheckBox(t("settings.start_minimized"))
        self.cb_minimized.setChecked(ui.get("start_minimized", False))
        self.cb_minimized.toggled.connect(
            lambda v: self._save("start_minimized", v))
        root.addWidget(self.cb_minimized)

        self.cb_notifications = QCheckBox(t("settings.notifications"))
        self.cb_notifications.setChecked(ui.get("notifications", True))
        self.cb_notifications.toggled.connect(
            lambda v: self._save("notifications", v))
        root.addWidget(self.cb_notifications)

        # --- Appearance -----------------------------------------------
        root.addWidget(self._section(t("settings.sec_appearance")))
        self.theme = QComboBox()
        self._theme_keys = ["dark", "light"]
        self.theme.addItem(t("settings.theme_dark"))
        self.theme.addItem(t("settings.theme_light"))
        cur_theme = ui.get("theme", DEFAULT_THEME)
        self.theme.setCurrentIndex(self._theme_keys.index(cur_theme)
                                   if cur_theme in self._theme_keys else 0)
        self.theme.currentIndexChanged.connect(self._on_theme)
        root.addLayout(self._labeled_row(t("settings.theme"), self.theme))

        self.accent = QComboBox()
        for key in _ACCENTS:
            self.accent.addItem(key.capitalize(), key)
        cur = ui.get("accent", DEFAULT_ACCENT)
        keys = list(_ACCENTS)
        self.accent.setCurrentIndex(keys.index(cur) if cur in keys else 0)
        self.accent.currentIndexChanged.connect(self._on_accent)
        root.addLayout(self._labeled_row(t("settings.accent"), self.accent))

        # --- Status colours (dot + tray per connection state) ---------
        root.addWidget(self._section(t("settings.sec_status")))
        for state_key, label_key in (
                ("connected", "settings.state_connected"),
                ("connecting", "settings.state_connecting"),
                ("disconnected", "settings.state_disconnected"),
                ("error", "settings.state_error")):
            root.addLayout(self._color_row(state_key, t(label_key)))

        # --- Behaviour (technical) ------------------------------------
        root.addWidget(self._section(t("settings.sec_behaviour")))
        self.on_exit = QComboBox()
        self._exit_keys = ["ask", "disconnect", "background"]
        for label in (t("settings.exit_ask"), t("settings.exit_disconnect"),
                      t("settings.exit_background")):
            self.on_exit.addItem(label)
        cur_exit = ("ask" if ui.get("ask_on_close", True)
                    else ui.get("close_action", "disconnect"))
        if cur_exit not in self._exit_keys:
            cur_exit = "ask"
        self.on_exit.setCurrentIndex(self._exit_keys.index(cur_exit))
        self.on_exit.currentIndexChanged.connect(self._on_exit_changed)
        root.addLayout(self._labeled_row(t("settings.on_exit"), self.on_exit))

        # --- Maintenance ----------------------------------------------
        root.addWidget(self._section(t("settings.sec_maintenance")))
        maint = QHBoxLayout()
        open_cfg = QPushButton(t("settings.open_config"))
        open_cfg.setObjectName("ghost")
        open_cfg.clicked.connect(
            lambda: _open_path(str(cfgmod.config_dir())))
        open_log = QPushButton(t("settings.open_log"))
        open_log.setObjectName("ghost")
        open_log.clicked.connect(
            lambda: _open_path(connect_log_path(str(cfgmod.config_path()))))
        maint.addWidget(open_cfg)
        maint.addWidget(open_log)
        maint.addStretch(1)
        root.addLayout(maint)

        # --- About / legal --------------------------------------------
        root.addWidget(self._section(t("settings.sec_about")))
        ver = QLabel(f"automatic VPN  v{_app_version()}")
        ver.setObjectName("sectionTitle")
        root.addWidget(ver)
        for key in ("settings.disclaimer", "settings.license"):
            lbl = QLabel(t(key))
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#9a9da3;")
            root.addWidget(lbl)

        about_btns = QHBoxLayout()
        repo = QPushButton(t("settings.open_repo"))
        repo.setObjectName("ghost")
        repo.clicked.connect(lambda: webbrowser.open(_REPO_URL))
        third = QPushButton(t("settings.third_party"))
        third.setObjectName("ghost")
        third.clicked.connect(self._show_third_party)
        about_btns.addWidget(repo)
        about_btns.addWidget(third)
        about_btns.addStretch(1)
        root.addLayout(about_btns)

        root.addStretch(1)
        back = QPushButton(t("btn.back"))
        back.setObjectName("primary")
        back.clicked.connect(lambda: self._on_back())
        root.addWidget(back)

    # --- helpers --------------------------------------------------------

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("sectionTitle")
        lbl.setContentsMargins(0, 12, 0, 2)
        return lbl

    def _labeled_row(self, label: str, widget: QWidget) -> QHBoxLayout:
        """A 'Label   [control]' row with an aligned label column and a
        fixed-width, left-aligned control (so combos don't stretch wide)."""
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(230)
        widget.setFixedWidth(240)
        row.addWidget(lbl)
        row.addWidget(widget)
        row.addStretch(1)
        return row

    def _color_row(self, state_key: str, label: str) -> QHBoxLayout:
        """A 'Label  [colour swatch]' row; the swatch opens a colour picker."""
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(230)
        swatch = QPushButton()
        swatch.setFixedSize(48, 24)
        swatch.setToolTip(t("settings.pick_color"))
        self._paint_swatch(swatch, _state_color(state_key))
        swatch.clicked.connect(lambda: self._pick_color(state_key, swatch))
        row.addWidget(lbl)
        row.addWidget(swatch)
        row.addStretch(1)
        return row

    @staticmethod
    def _paint_swatch(swatch: QPushButton, color: str) -> None:
        swatch.setStyleSheet(
            f"background:{color}; border:1px solid #888; border-radius:5px;")

    def _pick_color(self, state_key: str, swatch: QPushButton) -> None:
        from PyQt6.QtGui import QColor
        chosen = QColorDialog.getColor(QColor(_state_color(state_key)), self,
                                       t("settings.pick_color"))
        if not chosen.isValid():
            return
        data = cfgmod.load_config()
        data.setdefault("ui", {}).setdefault("state_colors", {})[state_key] = \
            chosen.name()
        try:
            cfgmod.save_config(data)
        except OSError:
            pass
        self._paint_swatch(swatch, chosen.name())

    def _save(self, key: str, value) -> None:
        data = cfgmod.load_config()
        data.setdefault("ui", {})[key] = value
        try:
            cfgmod.save_config(data)
        except OSError:
            pass

    def _on_autostart(self, enabled: bool) -> None:
        try:
            autostart.set_enabled(enabled)
        except Exception as exc:  # registry write failed
            QMessageBox.warning(self, t("settings.title"), str(exc))

    def _on_accent(self, idx: int) -> None:
        self._save("accent", self.accent.itemData(idx))
        if self._on_appearance_changed:
            self._on_appearance_changed()

    def _on_theme(self, idx: int) -> None:
        self._save("theme", self._theme_keys[idx])
        if self._on_appearance_changed:
            self._on_appearance_changed()

    def _on_exit_changed(self, idx: int) -> None:
        key = self._exit_keys[idx]
        data = cfgmod.load_config()
        ui = data.setdefault("ui", {})
        if key == "ask":
            ui["ask_on_close"] = True
        else:
            ui["ask_on_close"] = False
            ui["close_action"] = key
        try:
            cfgmod.save_config(data)
        except OSError:
            pass

    def _show_third_party(self) -> None:
        QMessageBox.information(self, t("settings.third_party"),
                                t("settings.third_party_text"))


class MainWindow(QWidget):
    def __init__(self, icon=None):
        super().__init__()
        self._icon = icon or QIcon()
        self.setWindowTitle("automatic VPN")
        outer = QVBoxLayout(self)

        # top bar (right-aligned): language selector. App settings live on
        # their own button in the control view (clearer than a stray gear).
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
        self.setup = SetupView(on_done=self._show_control,
                               on_cancel=self._show_control)
        self.control = ControlView(on_settings=self._show_setup,
                                   on_app_settings=self._show_settings)
        self.settings = SettingsView(
            on_back=self._show_control,
            on_appearance_changed=self._on_appearance_changed)
        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.control)
        self.stack.addWidget(self.settings)
        self._build_tray()
        self.control.on_state = self._update_tray
        self._last_state = None   # for one-shot state-change notifications

        # Global TOTP hotkey: types the current 6-digit code into the
        # focused field. Seed is pulled lazily from the keyring on each press.
        self._hotkey = totp_hotkey.TotpHotkey(self._current_totp_seed)
        self._apply_totp_hotkey()

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
        ic = _state_tray_icon(_state_color(state))
        if not ic.isNull():
            self.tray.setIcon(ic)
        tip = {"connected": t("tray.tip_connected"),
               "connecting": t("tray.tip_connecting"),
               "error": t("tray.tip_error"),
               "disconnected": t("tray.tip_disconnected")}.get(state, "")
        self.tray.setToolTip(f"automatic VPN — {tip}")
        if hasattr(self, "act_connect"):
            self.act_connect.setEnabled(state in ("disconnected", "error"))
            self.act_disconnect.setEnabled(state in ("connected", "connecting"))
        # Notify on real state changes (connected / disconnected / error).
        if state != self._last_state:
            msg = {"connected": t("tray.tip_connected"),
                   "disconnected": t("tray.tip_disconnected"),
                   "error": t("tray.tip_error")}.get(state)
            if msg and self._last_state is not None:
                self._notify("automatic VPN", msg)
            self._last_state = state

    def _notify(self, title: str, msg: str) -> None:
        """Show a tray balloon, honouring the notifications setting."""
        if self.tray is None:
            return
        if not (cfgmod.load_config().get("ui") or {}).get("notifications", True):
            return
        self.tray.showMessage(title, msg,
                              QSystemTrayIcon.MessageIcon.Information, 3000)

    def _show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit(self):
        if self._perform_exit_teardown():
            self._hotkey.stop()
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

    def _current_key(self) -> str:
        cur = self.stack.currentWidget()
        if cur is self.setup:
            return "setup"
        if cur is self.settings:
            return "settings"
        return "control"

    def _rebuild_views(self, current_key: str) -> None:
        """Recreate all three views (picks up new language / theme / accent
        and re-tints icons), then restore the active one."""
        if getattr(self, "control", None) is not None:
            self.control._timer.stop()
        for attr in ("setup", "control", "settings"):
            w = getattr(self, attr, None)
            if w is not None:
                self.stack.removeWidget(w)
                w.deleteLater()
        self.setup = SetupView(on_done=self._show_control,
                               on_cancel=self._show_control)
        self.control = ControlView(on_settings=self._show_setup,
                                   on_app_settings=self._show_settings)
        self.settings = SettingsView(
            on_back=self._show_control,
            on_appearance_changed=self._on_appearance_changed)
        self.control.on_state = self._update_tray
        self._last_state = None
        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.control)
        self.stack.addWidget(self.settings)
        target = {"setup": self.setup,
                  "settings": self.settings}.get(current_key, self.control)
        self.stack.setCurrentWidget(target)

    def _apply_language(self):
        """Re-create the views and re-label the chrome so the new language
        takes effect immediately."""
        self._rebuild_views(self._current_key())
        self.lang_label.setText(t("lang.label") + ":")
        if self.tray is not None:
            self.act_open.setText(t("tray.open"))
            self.act_connect.setText(t("btn.connect"))
            self.act_disconnect.setText(t("btn.disconnect"))
            self.act_quit.setText(t("tray.quit"))

    def _on_appearance_changed(self):
        """Theme or accent changed in Settings: restyle the app live and
        rebuild the views so the accent-tinted icons update too."""
        global _CURRENT_ACCENT
        ui = cfgmod.load_config().get("ui") or {}
        _CURRENT_ACCENT = ui.get("accent", DEFAULT_ACCENT)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_build_stylesheet(
                _CURRENT_ACCENT, ui.get("theme", DEFAULT_THEME)))
        self._rebuild_views("settings")

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
        # Returning from setup may have toggled the hotkey preference.
        self._apply_totp_hotkey()
        self.control.refresh()
        self.stack.setCurrentWidget(self.control)

    def _swap_setup(self):
        """Replace the setup view with a fresh instance so it reflects the
        current saved config and shows the Back button when appropriate."""
        idx = self.stack.indexOf(self.setup)
        new = SetupView(on_done=self._show_control,
                        on_cancel=self._show_control)
        self.stack.insertWidget(idx, new)
        self.stack.removeWidget(self.setup)
        self.setup.deleteLater()
        self.setup = new

    def _show_setup(self):
        self._swap_setup()
        self.stack.setCurrentWidget(self.setup)

    def _swap_settings(self):
        """Rebuild the settings view so it reflects the current state
        (autostart registry, accent, etc.) each time it opens."""
        idx = self.stack.indexOf(self.settings)
        new = SettingsView(on_back=self._show_control,
                           on_appearance_changed=self._on_appearance_changed)
        self.stack.insertWidget(idx, new)
        self.stack.removeWidget(self.settings)
        self.settings.deleteLater()
        self.settings = new

    def _show_settings(self):
        self._swap_settings()
        self.stack.setCurrentWidget(self.settings)

    # --- TOTP hotkey ----------------------------------------------------

    def _current_totp_seed(self) -> str:
        """Fetch the stored TOTP seed for the configured email (or '')."""
        av = (cfgmod.load_config().get("auto_vpn") or {})
        email = av.get("user_email", "")
        if not email:
            return ""
        try:
            return get_uni_totp_secret(email) or ""
        except Exception:
            return ""

    def _apply_totp_hotkey(self) -> None:
        """Start or stop the global TOTP hotkey per the saved preference."""
        enabled = (cfgmod.load_config().get("ui") or {}).get("totp_hotkey", True)
        if enabled:
            self._hotkey.start()
        else:
            self._hotkey.stop()

    # --- close behaviour ------------------------------------------------

    def closeEvent(self, event):
        """The window's X minimises to the tray (the app keeps running and
        is controlled from the tray icon). Real exit is via the tray's
        'Beenden'. If there is no system tray, fall back to exit teardown."""
        if self.tray is not None:
            event.ignore()
            self.hide()
            self._notify("automatic VPN", t("tray.minimized"))
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


def _app_version() -> str:
    """Version string for the About box. Tries installed package metadata,
    then the bundled ``__version__`` (the frozen exe carries no dist-info)."""
    try:
        from importlib.metadata import version
        return version("automatic-openconnect")
    except Exception:
        try:
            import automatic_openconnect
            return automatic_openconnect.__version__
        except Exception:
            return "dev"


def _open_path(path: str) -> None:
    """Open a file or folder in the OS file manager (best effort)."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        else:
            webbrowser.open("file://" + path)
    except Exception:
        pass


def _app_icon() -> QIcon:
    """Load the bundled app icon; empty QIcon if it cannot be found."""
    try:
        p = _ir.files("automatic_openconnect") / "assets" / "icon.ico"
        return QIcon(str(p))
    except Exception:
        return QIcon()


def _state_tray_icon(color_hex: str) -> QIcon:
    """Build the tray icon at runtime: a rounded tile in the given state
    colour with the white padlock glyph on top. Lets the status colours be
    fully user-configurable instead of shipping fixed coloured .ico files."""
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QPainter, QPixmap
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))
    painter.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), 14, 14)
    try:
        glyph = QPixmap(_asset_url("lock-glyph"))
        if not glyph.isNull():
            painter.drawPixmap(0, 0, glyph.scaled(
                size, size, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
    except Exception:
        pass
    painter.end()
    return QIcon(pm)


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
    global _CURRENT_ACCENT
    ui = (cfgmod.load_config().get("ui") or {})
    # Pick up the saved UI language (default English) before building widgets.
    i18n.set_lang(ui.get("lang", "en"))
    _CURRENT_ACCENT = ui.get("accent", DEFAULT_ACCENT)
    app = QApplication(sys.argv)
    app.setStyleSheet(_build_stylesheet(ui.get("accent", DEFAULT_ACCENT),
                                        ui.get("theme", DEFAULT_THEME)))
    # Keep the app alive when the window is closed — the tray icon controls
    # it. Real exit happens via the tray's "Beenden".
    app.setQuitOnLastWindowClosed(False)
    icon = _app_icon()
    app.setWindowIcon(icon)
    win = MainWindow(icon)
    win.setWindowIcon(icon)
    win.setMinimumSize(560, 520)
    win.resize(640, 560)
    # Start hidden in the tray if the user asked for it (and a tray exists);
    # otherwise show the window normally.
    if ui.get("start_minimized", False) and win.tray is not None:
        if ui.get("notifications", True):
            win.tray.showMessage(
                "automatic VPN", t("tray.started_hidden"),
                QSystemTrayIcon.MessageIcon.Information, 2500)
    else:
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
