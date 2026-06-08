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
import re
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
_SANS = "'Segoe UI', sans-serif"
_MONO = "'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono', monospace"
_COMIC = "'Comic Sans MS', 'Comic Sans', 'Chalkboard SE', cursive"
_PIXEL = "'Press Start 2P', 'Courier New', monospace"
# Anton — a free OFL Impact-like heavy sans (bundled in assets/fonts), used by
# the meme theme's headings. Falls back to Impact / a bold sans if unavailable.
_IMPACT = "'Anton', 'Impact', 'Arial Black', sans-serif"


def _load_bundled_fonts() -> None:
    """Register bundled .ttf fonts (assets/fonts) so themes can use them by
    family name. Needs a QApplication to exist; call once at startup."""
    try:
        from PyQt6.QtGui import QFontDatabase
        fdir = _ir.files("automatic_openconnect") / "assets" / "fonts"
        for entry in fdir.iterdir():
            name = str(entry)
            if name.lower().endswith(".ttf"):
                QFontDatabase.addApplicationFont(name)
    except Exception:
        pass

_PALETTES = {
    "dark": {
        "BG": "#1e1f22", "FG": "#e6e6e6", "SUB": "#9a9da3", "HEADER": "#ffffff",
        "PANEL": "#2b2d31", "BORDER": "#3a3d42", "HOVER": "#34373c",
        "DISFG": "#6b6e73", "DISBG": "#232427", "INDBORDER": "#5a5d63",
        "POPUPSEL": "#3a3d42", "LOGBG": "#141517",
        "FONT": _SANS, "PRIMARY_FG": "#ffffff",
    },
    "light": {
        "BG": "#f4f5f7", "FG": "#1c1d20", "SUB": "#5c5f66", "HEADER": "#101114",
        "PANEL": "#ffffff", "BORDER": "#cdd0d6", "HOVER": "#e8eaed",
        "DISFG": "#a3a6ac", "DISBG": "#e9eaec", "INDBORDER": "#aab0b8",
        "POPUPSEL": "#dfe2e7", "LOGBG": "#ffffff",
        "FONT": _SANS, "PRIMARY_FG": "#ffffff",
    },
    # Terminal / CRT: phosphor green on near-black, monospace, square corners
    # (the radius is zeroed in _build_stylesheet). Fits a tool that drives a
    # command-line VPN client. Accent is forced to phosphor green for cohesion.
    "terminal": {
        "BG": "#0a0f0a", "FG": "#74e792", "SUB": "#3f8a55", "HEADER": "#aaffc6",
        "PANEL": "#0f160f", "BORDER": "#1f3d29", "HOVER": "#15241a",
        "DISFG": "#2f5a3c", "DISBG": "#0c120c", "INDBORDER": "#2c5036",
        "POPUPSEL": "#1f3d29", "LOGBG": "#060906",
        "FONT": _MONO, "PRIMARY_FG": "#04140a",
    },
    # Nord — calm cool blue-grey (dark), frost accent. Professional, easy.
    "nord": {
        "BG": "#2e3440", "FG": "#d8dee9", "SUB": "#7b8494", "HEADER": "#eceff4",
        "PANEL": "#3b4252", "BORDER": "#434c5e", "HOVER": "#3f4858",
        "DISFG": "#6a7384", "DISBG": "#333a47", "INDBORDER": "#4c566a",
        "POPUPSEL": "#434c5e", "LOGBG": "#272c36",
        "FONT": _SANS, "PRIMARY_FG": "#2e3440",
    },
    # Plum — cozy warm aubergine/indigo (dark) with a coral accent.
    "plum": {
        "BG": "#221825", "FG": "#e9dcee", "SUB": "#9c8aa6", "HEADER": "#faf0ff",
        "PANEL": "#2d2132", "BORDER": "#3e2f45", "HOVER": "#382a3f",
        "DISFG": "#6e5e76", "DISBG": "#281d2d", "INDBORDER": "#4a394f",
        "POPUPSEL": "#3e2f45", "LOGBG": "#1a121e",
        "FONT": _SANS, "PRIMARY_FG": "#221825",
    },
    # Solarized — warm cream (light) with solar blue. Classic, comfortable.
    "solarized": {
        "BG": "#fdf6e3", "FG": "#586e75", "SUB": "#93a1a1", "HEADER": "#073642",
        "PANEL": "#eee8d5", "BORDER": "#ddd6c1", "HOVER": "#e7e0cb",
        "DISFG": "#a9a893", "DISBG": "#ece5d0", "INDBORDER": "#c8c0a8",
        "POPUPSEL": "#e7e0cb", "LOGBG": "#fbf3df",
        "FONT": _SANS, "PRIMARY_FG": "#fdf6e3",
    },
    # Sand — paper off-white (light), terracotta accent. Editorial, premium.
    "sand": {
        "BG": "#f5f0e6", "FG": "#3a352c", "SUB": "#837b6c", "HEADER": "#211d15",
        "PANEL": "#fffdf6", "BORDER": "#ddd4c2", "HOVER": "#ece5d5",
        "DISFG": "#b0a892", "DISBG": "#ebe4d4", "INDBORDER": "#c9bea4",
        "POPUPSEL": "#ece5d5", "LOGBG": "#fffdf6",
        "FONT": _SANS, "PRIMARY_FG": "#ffffff",
    },
    # --- bold / artsy themes (loud colours + character fonts) -------------
    # Y2K — early-2000s Web 2.0: aqua/blue, Comic Sans, glossy buttons.
    "y2k": {
        "BG": "#dff1ff", "FG": "#0a3d62", "SUB": "#3c79a8", "HEADER": "#0652dd",
        "PANEL": "#ffffff", "BORDER": "#8fd0ef", "HOVER": "#cdeaff",
        "DISFG": "#8fb4cf", "DISBG": "#e6f4ff", "INDBORDER": "#7ec8e3",
        "POPUPSEL": "#cdeaff", "LOGBG": "#f2fbff",
        "FONT": _COMIC, "PRIMARY_FG": "#ffffff",
    },
    # Kawaii — pastel anime: candy pink + lavender, Comic Sans, very rounded.
    "kawaii": {
        "BG": "#ffe9f3", "FG": "#7a4a63", "SUB": "#c489a6", "HEADER": "#d6336c",
        "PANEL": "#fff5fa", "BORDER": "#ffc2da", "HOVER": "#ffd9e9",
        "DISFG": "#d9aec0", "DISBG": "#ffeef5", "INDBORDER": "#ffb3d1",
        "POPUPSEL": "#ffd9e9", "LOGBG": "#fff5fa",
        "FONT": _COMIC, "PRIMARY_FG": "#ffffff",
    },
    # Meme — deep-fried oversaturated warmth: hot orange on near-black, Anton
    # headings + bold white-with-black-outline meme text. Loud and fun.
    "meme": {
        "BG": "#1a0f06", "FG": "#ffe9c2", "SUB": "#d8954a", "HEADER": "#ffffff",
        "PANEL": "#2a1608", "BORDER": "#7a3a0c", "HOVER": "#3a1d0a",
        "DISFG": "#8a5a30", "DISBG": "#21130a", "INDBORDER": "#a8500f",
        "POPUPSEL": "#7a3a0c", "LOGBG": "#120a04",
        "FONT": _SANS, "PRIMARY_FG": "#1a0f06",
    },
    # Pixel — Game Boy DMG greens, pixel font, square + chunky.
    "pixel": {
        "BG": "#0f380f", "FG": "#9bbc0f", "SUB": "#6b8c1a", "HEADER": "#c6de4a",
        "PANEL": "#214b21", "BORDER": "#306230", "HOVER": "#2a5a2a",
        "DISFG": "#4a6b1f", "DISBG": "#143614", "INDBORDER": "#306230",
        "POPUPSEL": "#306230", "LOGBG": "#0a2a0a",
        "FONT": _PIXEL, "PRIMARY_FG": "#0f380f",
    },
}
DEFAULT_THEME = "dark"

# Themes painted square (no rounded corners).
_SQUARE_THEMES = {"terminal", "pixel"}

# Themes with an animated PAINTED backdrop (scene name → _Backdrop._scene_*).
# A theme listed in _THEME_GIF prefers its GIF; the painted scene here is the
# graceful fallback when the GIF asset is missing.
_THEME_BACKDROP = {
    "kawaii": "hearts",
    "y2k": "bubbles",
    "pixel": "pixels",
    "meme": "deepfried",
}

# Themes whose backdrop is an animated GIF (theme → asset basename under
# assets/backgrounds/<name>.gif), played via QMovie and paused when hidden.
# Falls back to the painted scene in _THEME_BACKDROP if the file is missing.
_THEME_GIF = {
    "kawaii": "kawaii",
    "meme": "meme",
}

# Themes that force their own cohesive accent (the accent picker only applies
# to Dark/Light). Values are (base, hover).
_THEME_ACCENTS = {
    "terminal":  ("#33ff66", "#28cc52"),   # phosphor green
    "nord":      ("#88c0d0", "#7badbf"),   # frost blue
    "plum":      ("#ff8a65", "#f5734a"),   # coral
    "solarized": ("#268bd2", "#1f72ad"),   # solar blue
    "sand":      ("#c1654a", "#a8543c"),   # terracotta
    "y2k":       ("#00a8ff", "#0097e6"),   # aqua
    "kawaii":    ("#ff6fa5", "#ff4f90"),   # candy pink
    "pixel":     ("#d818c8", "#bc12ad"),   # vibrant arcade magenta (not green)
    "meme":      ("#39e639", "#2bcc2b"),   # stonks green
}

# Per-theme EXTRA stylesheet appended after the base — for the bold/artsy
# flourishes (glossy gradient buttons, extra-round corners) that don't fit the
# plain token swap. Self-contained selectors only, so the base stays intact.
_THEME_EXTRA_QSS = {
    # Y2K — turn-of-the-millennium chrome: glossy aqua buttons, Comic Sans
    # body, hazard-stripe footer hint. The WordArt header is painted by
    # _WordArtLabel (the real header text is hidden via _Backdrop overlay).
    "y2k": """
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #7fd4ff, stop:0.5 #00a8ff, stop:1 #0077c2);
    border: 1px solid #0077c2; border-radius: 11px; font-weight: 700; }
QPushButton { border-radius: 11px; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #ffffff, stop:1 #e3f3ff); }
QLabel#subheader { color: #c0157a; font-weight: 700; }
""",
    "kawaii": """
QPushButton, QLineEdit, QComboBox { border-radius: 16px; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #ffa6c9, stop:1 #ff6fa5); border: none; border-radius: 18px; }
QCheckBox::indicator { border-radius: 8px; }
""",
    # Meme — deep-fried + bold. Anton heading, chunky stonks-green primary
    # button. The header gets the white-text/black-outline meme treatment via
    # _MemeLabel; everything else stays loud but readable.
    "meme": """
QLabel#header { font-family: @IMPACT@; font-size: 30px;
    letter-spacing: 1px; color: #ffffff; }
QLabel#sectionTitle { font-family: @IMPACT@; font-size: 17px; color: #ffd24a; }
QLabel#subheader { color: #ffb84a; font-weight: 700; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #5cff5c, stop:1 #1faa1f); border: 2px solid #0a3d0a;
    color: #08240a; font-weight: 800; }
QPushButton { border: 2px solid #b85a14; font-weight: 700; }
""",
    # Press Start 2P is large + blocky → scale every size down for the pixel UI.
    "pixel": """
QWidget { font-size: 10px; }
QLabel#header { font-size: 15px; }
QLabel#statusText { font-size: 12px; }
QLabel#subheader { font-size: 9px; }
QPushButton#primary { font-size: 11px; }
QPushButton { padding: 10px 14px; }
""",
}

# Current accent + theme — used to tint action icons (the stylesheet handles
# the rest). Terminal theme tints icons phosphor green regardless of accent.
_CURRENT_ACCENT = DEFAULT_ACCENT
_CURRENT_THEME = DEFAULT_THEME

_STYLESHEET_TMPL = """
QWidget { background-color: @BG@; color: @FG@;
          font-family: @FONT@; font-size: 13px; }
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
                      color: @PRIMARY_FG@; font-weight: 600; font-size: 15px; }
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


def _gif_path(name: str) -> str:
    """Absolute path to a bundled backdrop GIF, or '' if it isn't present
    (so a theme can fall back to its painted scene). Uses the same
    importlib.resources mechanism as the bundled fonts/icons."""
    try:
        p = _ir.files("automatic_openconnect") / "assets" / "backgrounds" \
            / f"{name}.gif"
        return str(p) if os.path.exists(str(p)) else ""
    except Exception:
        return ""


def _build_stylesheet(accent: str = DEFAULT_ACCENT,
                      theme: str = DEFAULT_THEME) -> str:
    pal = _PALETTES.get(theme, _PALETTES[DEFAULT_THEME])
    if theme in _THEME_ACCENTS:
        base, hover = _THEME_ACCENTS[theme]   # cohesive per-theme accent
    else:
        base, hover = _ACCENTS.get(accent, _ACCENTS[DEFAULT_ACCENT])
    s = _STYLESHEET_TMPL
    for key, value in pal.items():
        s = s.replace(f"@{key}@", value)
    s = s.replace("@ACCENT_HOVER@", hover).replace("@ACCENT@", base)
    s = s.replace("@CHEVRON@", _asset_url("chevron"))
    s = s.replace("@CHECK@", _asset_url("check"))
    if theme in _SQUARE_THEMES:
        # Square everything for the CRT / pixel look.
        s = re.sub(r"border-radius:\s*\d+px", "border-radius: 0px", s)
    # Bold/artsy flourishes (glossy buttons, extra-round corners) appended last.
    s += _THEME_EXTRA_QSS.get(theme, "")
    s = s.replace("@IMPACT@", _IMPACT)   # meme heading font family
    if theme in _THEME_BACKDROP:
        # Let the animated backdrop show through: containers + labels go
        # transparent (the backdrop paints its own dimming scrim so text stays
        # readable), while input cards keep their bg and the log / dialogs /
        # menus stay opaque (dialogs are separate top-level windows).
        s += (
            "\nQStackedWidget, QScrollArea, QFrame, QLabel, QCheckBox,"
            " ControlView, SetupView, SettingsView, PrereqPanel"
            " { background: transparent; }\n"
            f"QPlainTextEdit {{ background-color: {pal['LOGBG']}; }}\n"
            f"QDialog, QMenu, QToolTip {{ background-color: {pal['PANEL']}; }}\n"
        )
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
    if _CURRENT_THEME in _THEME_ACCENTS:
        base = _THEME_ACCENTS[_CURRENT_THEME][0]   # matches the theme's accent
    else:
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


class _FancyHeader(QLabel):
    """The app title, with an over-the-top per-theme treatment painted via
    QPainter for the loudest artsy themes:

      * ``y2k``  — classic WordArt: a rainbow GRADIENT fill, a chunky dark
        bevel/outline and a drop shadow, slightly arched.
      * ``meme`` — top/bottom-text meme style: bold WHITE fill with a thick
        BLACK outline + drop shadow (Anton if bundled).

    Any other theme falls through to a normal QLabel (the stylesheet styles
    ``QLabel#header``), so this is purely additive for the bold themes."""

    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("header")
        self._fancy = _CURRENT_THEME in ("y2k", "meme")
        if self._fancy:
            # reserve vertical room for the shadow/outline + arch
            self.setMinimumHeight(58)

    def _font(self):
        from PyQt6.QtGui import QFont
        if _CURRENT_THEME == "meme":
            f = QFont("Anton", 30)
            f.setStyleHint(QFont.StyleHint.SansSerif)
        else:  # y2k WordArt
            f = QFont("Arial Black", 30)
            f.setBold(True)
        return f

    def paintEvent(self, e):
        if not self._fancy:
            super().paintEvent(e)
            return
        from PyQt6.QtGui import (QPainter, QColor, QPen, QPainterPath,
                                 QLinearGradient, QBrush, QFontMetrics)
        text = self.text()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        font = self._font()
        p.setFont(font)
        fm = QFontMetrics(font)
        baseline = (self.height() + fm.ascent() - fm.descent()) // 2
        x = 2
        if _CURRENT_THEME == "y2k":
            self._paint_wordart(p, text, x, baseline, fm)
        else:
            self._paint_meme(p, text, x, baseline, fm)
        p.end()

    def _paint_wordart(self, p, text, x, baseline, fm):
        """Rainbow-gradient fill + dark bevel + drop shadow, gently arched —
        the unmistakable early-2000s WordArt look."""
        from PyQt6.QtGui import (QColor, QPen, QPainterPath, QLinearGradient,
                                 QBrush)
        import math
        # build one path per character so we can arch the baseline
        full = QPainterPath()
        cx = x
        n = max(1, len(text))
        for i, ch in enumerate(text):
            arch = -int(8 * math.sin(math.pi * i / (n - 1 or 1)))
            sub = QPainterPath()
            sub.addText(float(cx), float(baseline + arch), p.font(), ch)
            full.addPath(sub)
            cx += fm.horizontalAdvance(ch)
        # drop shadow
        sh = QPainterPath(full)
        sh.translate(3, 4)
        p.fillPath(sh, QColor(0, 0, 0, 110))
        # dark bevel outline
        pen = QPen(QColor("#0a2a5e")); pen.setWidth(5)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(full)
        # rainbow gradient fill (the WordArt classic)
        grad = QLinearGradient(0, 0, cx, 0)
        for stop, col in ((0.0, "#ff2d2d"), (0.2, "#ff9e1f"), (0.4, "#ffe600"),
                          (0.6, "#2bd84a"), (0.8, "#2d8bff"), (1.0, "#b14dff")):
            grad.setColorAt(stop, QColor(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(full, QBrush(grad))
        # a glossy top highlight band
        hi = QLinearGradient(0, baseline - fm.ascent(), 0, baseline)
        hi.setColorAt(0.0, QColor(255, 255, 255, 160))
        hi.setColorAt(0.45, QColor(255, 255, 255, 0))
        p.fillPath(full, QBrush(hi))

    def _paint_meme(self, p, text, x, baseline, fm):
        """Bold WHITE fill with a thick BLACK outline + drop shadow."""
        from PyQt6.QtGui import QColor, QPen, QPainterPath
        path = QPainterPath()
        path.addText(float(x), float(baseline), p.font(), text)
        sh = QPainterPath(path)
        sh.translate(2, 3)
        p.fillPath(sh, QColor(0, 0, 0, 120))
        pen = QPen(QColor("#000000")); pen.setWidth(6)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path, QColor("#ffffff"))


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


class PrereqPanel(QWidget):
    """Prerequisites checklist with inline one-click fixes.

    Reusable in two places so the install actions live where the user is:
      * embedded in the setup form (``inline=True``) — the single setup
        surface, so there's no jump to a separate dialog;
      * inside :class:`PreflightDialog` (``inline=False``) — the quick check
        reachable from the control view.

    Reads the current email / openconnect / openconnect-sso values through
    getter callables, so it stays in sync with the form fields as they're
    edited or Browsed.
    """

    def __init__(self, parent, get_email, get_oc, get_sso, *,
                 inline=False, on_setup=None):
        super().__init__(parent)
        self._get_email = get_email
        self._get_oc = get_oc
        self._get_sso = get_sso
        self._inline = inline
        self._on_setup = on_setup
        self._proc = None
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._rebuild()
        # Live re-check: reflect reality every few seconds (after an install,
        # a Browse…, or creating the config) without a manual refresh.
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._tick)
        self._poll.start(2500)

    def _checks(self):
        checks = preflight.check_all(self._get_email() or None,
                                     self._get_oc(), self._get_sso())
        if self._inline:
            # Credentials are entered in the form right above this panel —
            # listing them here (with a "Go to setup" jump) is the very
            # back-and-forth we're removing.
            checks = [c for c in checks if c.name != "check.credentials"]
        return checks

    def all_ok(self) -> bool:
        return preflight.all_ok(self._checks())

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
        checks = self._checks()
        for c in checks:
            self._root.addWidget(self._row(c))
        foot = QLabel(t("preflight.all_ok") if preflight.all_ok(checks)
                      else t("preflight.todo"))
        foot.setObjectName("subheader")
        self._root.addWidget(foot)

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
            # non-standard install location auto-detection missed. Inline, the
            # path field's own Browse… button already does this.
            if c.name == "check.openconnect" and not self._inline:
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

    def _locate_openconnect(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("preflight.locate"), "",
            "openconnect.exe (openconnect.exe);;Programs (*.exe);;All files (*)")
        if not path:
            return
        path = gl.normalize_openconnect_path(path)  # gui.exe → openconnect.exe
        # Persist so setup and the backend use it, then re-check live.
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


class PreflightDialog(QDialog):
    """Standalone prerequisites checklist — a thin wrapper hosting a
    :class:`PrereqPanel` (used by the control view's quick check)."""

    def __init__(self, parent, email, oc_path, sso_path, on_setup=None):
        super().__init__(parent)
        self._on_setup = on_setup
        self.setWindowTitle(t("preflight.title"))
        self.resize(720, 460)
        root = QVBoxLayout(self)
        self.panel = PrereqPanel(self, lambda: email, lambda: oc_path,
                                 lambda: sso_path, inline=False,
                                 on_setup=self._go_setup)
        root.addWidget(self.panel)
        root.addStretch(1)
        close_btn = QPushButton(t("preflight.close"))
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn)

    def _go_setup(self):
        if self._on_setup:
            self._on_setup()
        self.accept()


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

        # Prerequisites live HERE in the form (Option B): install the login
        # helper / create the config / see what's missing in one place — no
        # jump to a separate dialog.
        prereq_head = QLabel(t("preflight.title"))
        prereq_head.setStyleSheet("font-weight:600; margin-top:8px;")
        form.addRow(prereq_head)
        self.prereq_panel = PrereqPanel(
            self,
            get_email=lambda: self.email.text(),
            get_oc=lambda: self.oc.text(),
            get_sso=lambda: self.sso.text(),
            inline=True)
        form.addRow(self.prereq_panel)

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

        header = _FancyHeader("automatic VPN")
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
        self._theme_keys = ["dark", "light", "nord", "plum", "solarized",
                            "sand", "terminal", "y2k", "kawaii", "pixel",
                            "meme"]
        for _tk in self._theme_keys:
            self.theme.addItem(t(f"settings.theme_{_tk}"))
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


class _Backdrop(QWidget):
    """Animated background for the artsy themes. Two modes:

      * a PAINTED scene (drawn via QPainter, recolours with the theme), or
      * an animated GIF (played via QMovie) when the theme declares one.

    Mouse-transparent; fills the parent and lays a dimming scrim over the GIF
    (the painted scenes draw their own) so foreground text stays readable.
    Animation is paused whenever the window is hidden/minimised — for the GIF
    that means QMovie is actually stopped — so an idle app costs 0% CPU."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._scene = None
        self._pal = {}
        self._t = 0.0
        self._movie = None        # QMovie when this theme uses a GIF backdrop
        self._scrim_hex = "#000000"
        import random
        rnd = random.Random(20260607)
        # (x0..1, phase0..1, size0..1, speed0..1) — stable layout per element.
        self._blobs = [(rnd.random(), rnd.random(), rnd.random(), rnd.random())
                       for _ in range(40)]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_scene(self, scene, palette, gif=None, scrim_hex="#000000"):
        """Activate a backdrop. ``gif`` is an absolute path to a looping GIF
        (preferred when present); otherwise the painted ``scene`` is used.
        Either may be falsy to disable the backdrop entirely."""
        self._stop_movie()
        self._scene = scene
        self._pal = palette or {}
        self._scrim_hex = scrim_hex
        if gif:
            self._start_movie(gif)
            self.show()
            self.lower()
            self._timer.stop()    # QMovie drives its own repaints
        elif scene:
            self.show()
            self.lower()
            if not self._timer.isActive():
                self._timer.start(66)   # ~15 fps — smooth + light on CPU
        else:
            self._timer.stop()
            self.hide()
        self.update()

    def _start_movie(self, path):
        from PyQt6.QtGui import QMovie
        mv = QMovie(path)
        if not mv.isValid():
            self._movie = None     # graceful fallback to the painted scene
            return
        mv.frameChanged.connect(self.update)   # repaint each GIF frame
        mv.start()
        self._movie = mv

    def _stop_movie(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie = None

    def _tick(self):
        self._t += 1.0
        self.update()

    def pause(self):
        """Stop animating (window minimised / hidden to tray) → 0% CPU while
        idle, which is the app's normal state. Stops the GIF too."""
        self._timer.stop()
        if self._movie is not None:
            self._movie.setPaused(True)

    def resume(self):
        """Resume animating, but only if a backdrop is active."""
        if self._movie is not None:
            self._movie.setPaused(False)
        elif self._scene and not self._timer.isActive():
            self._timer.start(66)

    def paintEvent(self, _e):
        from PyQt6.QtGui import QPainter
        # GIF backdrop: draw the current frame scaled to fill, then a scrim.
        if self._movie is not None:
            pm = self._movie.currentPixmap()
            if not pm.isNull():
                p = QPainter(self)
                scaled = pm.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                p.drawPixmap(x, y, scaled)
                self._scrim(p, self._scrim_hex, 90)
                p.end()
            return
        if not self._scene:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            getattr(self, f"_scene_{self._scene}")(p)
        except Exception:
            pass
        p.end()

    def _vgrad(self, top, bottom):
        from PyQt6.QtGui import QLinearGradient, QColor
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, QColor(top))
        g.setColorAt(1.0, QColor(bottom))
        return g

    def _scrim(self, p, hexcol, alpha):
        from PyQt6.QtGui import QColor
        c = QColor(hexcol)
        c.setAlpha(alpha)
        p.fillRect(self.rect(), c)

    # --- scenes ----------------------------------------------------------

    def _heart(self, cx, cy, s):
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.32)
        path.cubicTo(cx - s, cy - s * 0.3, cx - s * 0.55, cy - s, cx, cy - s * 0.38)
        path.cubicTo(cx + s * 0.55, cy - s, cx + s, cy - s * 0.3, cx, cy + s * 0.32)
        return path

    def _sparkle(self, p, cx, cy, s, col):
        """A 4-point twinkle star (kawaii sticker style)."""
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        k = s * 0.26          # waist of the star arms
        path.moveTo(cx, cy - s)
        path.cubicTo(cx + k, cy - k, cx + k, cy - k, cx + s, cy)
        path.cubicTo(cx + k, cy + k, cx + k, cy + k, cx, cy + s)
        path.cubicTo(cx - k, cy + k, cx - k, cy + k, cx - s, cy)
        path.cubicTo(cx - k, cy - k, cx - k, cy - k, cx, cy - s)
        p.setBrush(col)
        p.drawPath(path)

    def _scene_hearts(self, p):     # kawaii: hearts + sparkles + bokeh
        from PyQt6.QtGui import QColor, QRadialGradient, QLinearGradient, QBrush
        import math
        w, h = self.width(), self.height()
        # bolder candy gradient: peach → pink → lavender, on a diagonal
        g = QLinearGradient(0, 0, w, h)
        g.setColorAt(0.0, QColor("#ffd9ec"))
        g.setColorAt(0.5, QColor("#ffb3da"))
        g.setColorAt(1.0, QColor("#d6c2ff"))
        p.fillRect(self.rect(), QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        # soft out-of-focus bokeh — big translucent circles drifting up slowly
        for (bx, ph, sz, sp) in self._blobs[:14]:
            br = 28 + sz * 90
            x = bx * w + math.sin(self._t * 0.02 + ph * 6.283) * 26
            y = h + br - ((self._t * (0.18 + sp * 0.5) + ph * (h + 200))
                          % (h + 2 * br))
            bok = QRadialGradient(x, y, br)
            tint = "#fff0fa" if ph > 0.5 else "#efe6ff"
            c0 = QColor(tint); c0.setAlpha(70)
            c1 = QColor(tint); c1.setAlpha(0)
            bok.setColorAt(0.0, c0); bok.setColorAt(1.0, c1)
            p.setBrush(bok)
            p.drawEllipse(int(x - br), int(y - br), int(2 * br), int(2 * br))
        # foreground: hearts and stars, swaying as they rise
        palette = ["#ff5fa2", "#ff8fbf", "#b98bff", "#ff9ecf"]
        for i, (bx, ph, sz, sp) in enumerate(self._blobs):
            s = 9 + sz * 24
            sway = math.sin(self._t * 0.05 + ph * 6.283) * (10 + sz * 26)
            x = bx * w + sway
            y = h + s - ((self._t * (0.7 + sp * 1.9) + ph * (h + 80))
                         % (h + 2 * s))
            col = QColor(palette[i % len(palette)]); col.setAlpha(180)
            if i % 3 == 0:                      # ~1/3 are twinkle stars
                spin = 0.85 + 0.15 * math.sin(self._t * 0.18 + ph * 6.283)
                self._sparkle(p, x, y, s * spin, col)
            else:
                p.setBrush(col)
                p.drawPath(self._heart(x, y, s))
        # tiny white glints scattered for extra sparkle
        for (bx, ph, sz, sp) in self._blobs[::3]:
            tw_ = 0.5 + 0.5 * math.sin(self._t * 0.2 + ph * 12 + bx * 7)
            gx = (bx * 1.7 % 1.0) * w
            gy = ((ph * 1.3 + self._t * 0.004) % 1.0) * h
            c = QColor("#ffffff"); c.setAlpha(int(120 * tw_))
            self._sparkle(p, gx, gy, 3 + sz * 4, c)
        self._scrim(p, "#fff0f6", 60)

    def _starburst(self, p, cx, cy, R, col, spikes=4):
        """A chunky Web-1.0 lens-flare: long thin spikes + a bright core."""
        from PyQt6.QtGui import QColor, QPainterPath
        import math
        for k in range(spikes):
            ang = math.pi * k / spikes
            dx, dy = math.cos(ang), math.sin(ang)
            wdt = max(2.0, R * 0.06)
            path = QPainterPath()
            path.moveTo(cx + dy * wdt, cy - dx * wdt)
            path.lineTo(cx + dx * R, cy + dy * R)
            path.lineTo(cx - dy * wdt, cy + dx * wdt)
            path.lineTo(cx - dx * R, cy - dy * R)
            path.closeSubpath()
            p.setBrush(col)
            p.drawPath(path)

    def _hazard_band(self, p, y, band_h, scroll, col_a, col_b, stripe=22):
        """A diagonal "Under Construction" hazard-stripe band across the full
        width — the loudest possible turn-of-the-millennium flourish."""
        from PyQt6.QtGui import QColor, QPainterPath
        w = self.width()
        p.save()
        clip = QPainterPath()
        clip.addRect(0.0, float(y), float(w), float(band_h))
        p.setClipPath(clip)
        off = int(scroll) % (2 * stripe)
        x = -band_h - 2 * stripe + off
        i = 0
        while x < w + band_h:
            col = QColor(col_a if i % 2 == 0 else col_b)
            poly = QPainterPath()
            poly.moveTo(x, y + band_h)
            poly.lineTo(x + stripe, y + band_h)
            poly.lineTo(x + stripe + band_h, y)
            poly.lineTo(x + band_h, y)
            poly.closeSubpath()
            p.fillPath(poly, col)
            x += stripe
            i += 1
        p.restore()

    def _scene_bubbles(self, p):    # y2k: hazard stripes + starfield + shine
        from PyQt6.QtGui import QColor, QRadialGradient, QBrush
        import math
        w, h = self.width(), self.height()
        # chunky 2000s aqua radial backdrop (light → saturated edges)
        bg = QRadialGradient(w * 0.5, h * 0.42, max(w, h) * 0.75)
        bg.setColorAt(0.0, QColor("#f4fbff"))
        bg.setColorAt(0.55, QColor("#cfeeff"))
        bg.setColorAt(1.0, QColor("#8fd0ff"))
        p.fillRect(self.rect(), QBrush(bg))
        p.setPen(Qt.PenStyle.NoPen)
        # scrolling "Under Construction" hazard stripes top + bottom
        bh = max(14, int(h * 0.05))
        self._hazard_band(p, 0, bh, self._t * 1.4, "#ffd400", "#1a1a1a")
        self._hazard_band(p, h - bh, bh, -self._t * 1.4, "#ffd400", "#1a1a1a")
        # drifting starfield — clashing neon diamonds streaming right→left
        neon = ["#00a8ff", "#ff00d4", "#39ff14", "#ffffff", "#ff7a00"]
        for i, (bx, ph, sz, sp) in enumerate(self._blobs):
            s = 3 + sz * 8
            x = ((bx + self._t * (0.0015 + sp * 0.004)) % 1.0) * w
            x = w - x                       # drift right→left
            y = bh + ph * (h - 2 * bh)      # keep clear of the hazard bands
            twk = 0.5 + 0.5 * math.sin(self._t * 0.15 + ph * 9 + bx * 5)
            c = QColor(neon[i % len(neon)])
            c.setAlpha(int(70 + 150 * twk))
            self._starburst(p, x, y, s, c, spikes=2 + (i % 2) * 2)
        # one big rotating lens-flare in the upper area (the Web-1.0 "shine")
        fx = w * (0.32 + 0.12 * math.sin(self._t * 0.012))
        fy = h * 0.30
        R = max(60, int(min(w, h) * 0.22))
        halo = QRadialGradient(fx, fy, R * 1.4)
        halo.setColorAt(0.0, QColor(255, 255, 255, 180))
        halo.setColorAt(0.4, QColor(160, 220, 255, 90))
        halo.setColorAt(1.0, QColor(160, 220, 255, 0))
        p.setBrush(halo)
        p.drawEllipse(int(fx - R * 1.4), int(fy - R * 1.4),
                      int(R * 2.8), int(R * 2.8))
        spin = self._t * 0.03
        p.save()
        p.translate(fx, fy)
        p.rotate(math.degrees(spin))
        glint = QColor(255, 255, 255, 210)
        self._starburst(p, 0, 0, R, glint, spikes=4)
        p.restore()
        core = QRadialGradient(fx, fy, R * 0.28)
        core.setColorAt(0.0, QColor(255, 255, 255, 235))
        core.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(core)
        p.drawEllipse(int(fx - R * 0.28), int(fy - R * 0.28),
                      int(R * 0.56), int(R * 0.56))
        # a couple of small secondary flares along the flare axis
        for off, rr in ((0.55, 0.10), (1.25, 0.06), (-0.4, 0.05)):
            sx = fx + (w * 0.5 - fx) * off
            sy = fy + (h * 0.5 - fy) * off
            sr = R * rr
            sc = QColor(0, 168, 255, 70)
            p.setBrush(sc)
            p.drawEllipse(int(sx - sr), int(sy - sr), int(2 * sr), int(2 * sr))
        self._scrim(p, "#eaf6ff", 66)

    # Tetromino-ish shapes on a 2x2 cell grid — the classic 8-bit block look.
    _PIX_SHAPES = (
        ((0, 0), (1, 0), (0, 1), (1, 1)),   # O (square)
        ((0, 0), (1, 0), (2, 0), (1, 1)),   # T
        ((0, 0), (0, 1), (1, 1), (2, 1)),   # J
        ((0, 0), (1, 0), (2, 0), (3, 0)),   # I
        ((1, 0), (2, 0), (0, 1), (1, 1)),   # S
    )

    def _scene_pixels(self, p):     # pixel: 8-bit Game Boy falling blocks
        from PyQt6.QtGui import QColor
        import math
        w, h = self.width(), self.height()
        # the 4 classic DMG screen shades (darkest → lightest)
        dark, mid, light, lite = "#0f380f", "#306230", "#8bac0f", "#9bbc0f"
        p.fillRect(self.rect(), QColor(dark))
        p.setPen(Qt.PenStyle.NoPen)
        # --- dithered checker backdrop (snapped to a chunky pixel grid) ---
        cell = 16
        # offset the dither so it gently scrolls (LCD "ghosting" vibe)
        scroll = int(self._t * 0.5) % (2 * cell)
        c_dither = QColor(mid); c_dither.setAlpha(45)
        p.setBrush(c_dither)
        ny = h // cell + 2
        nx = w // cell + 2
        for gy in range(ny):
            for gx in range(nx):
                if (gx + gy) % 2 == 0:
                    p.fillRect(gx * cell, gy * cell - scroll, cell, cell,
                               c_dither)
        shades = (light, mid, lite, light)
        # --- falling tetromino blocks (snapped to the pixel grid) ---------
        for i, (bx, ph, sz, sp) in enumerate(self._blobs):
            unit = 8 + int(sz * 8)
            unit -= unit % 4 or 4           # snap unit to 4px
            shape = self._PIX_SHAPES[i % len(self._PIX_SHAPES)]
            span = h + 6 * unit
            x0 = int((bx * w) // unit * unit)
            y0 = int((h + 2 * unit
                      - ((self._t * (0.5 + sp * 1.3) + ph * span) % span))
                     // unit * unit)
            col = QColor(shades[i % len(shades)])
            col.setAlpha(150)
            hi = QColor(lite); hi.setAlpha(170)     # top/left bevel
            for (dx, dy) in shape:
                bx0, by0 = x0 + dx * unit, y0 + dy * unit
                p.fillRect(bx0, by0, unit, unit, col)
                # a 2px highlight edge gives each block a chunky 3D bevel
                p.fillRect(bx0, by0, unit, 2, hi)
                p.fillRect(bx0, by0, 2, unit, hi)
        # --- twinkling "power pixels": bright single cells ----------------
        for (bx, ph, sz, sp) in self._blobs[::4]:
            twk = 0.5 + 0.5 * math.sin(self._t * 0.25 + ph * 11 + bx * 6)
            if twk < 0.55:
                continue
            px = int((bx * w) // 8 * 8)
            py = int((((ph + self._t * 0.002) % 1.0) * h) // 8 * 8)
            c = QColor(lite); c.setAlpha(int(120 + 120 * twk))
            p.fillRect(px, py, 8, 8, c)
        self._scrim(p, "#0f380f", 78)

    def _scene_deepfried(self, p):  # meme fallback: pulsing glow + stonks arrow
        from PyQt6.QtGui import QColor, QRadialGradient, QBrush, QPainterPath
        import math
        w, h = self.width(), self.height()
        # deep-fried warm glow that pulses (orange core breathing in/out)
        pulse = 0.5 + 0.5 * math.sin(self._t * 0.06)
        glow = QRadialGradient(w * 0.5, h * 0.55, max(w, h) * (0.6 + 0.12 * pulse))
        glow.setColorAt(0.0, QColor(int(255), int(120 - 60 * pulse), 30))
        glow.setColorAt(0.55, QColor("#b5300a"))
        glow.setColorAt(1.0, QColor("#28083c"))
        p.fillRect(self.rect(), QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        # scattered deep-fried sparkles
        for i, (bx, ph, sz, sp) in enumerate(self._blobs):
            twk = 0.5 + 0.5 * math.sin(self._t * 0.2 + ph * 9 + bx * 6)
            r = 1 + sz * 3
            c = QColor(255, 240, 120); c.setAlpha(int(50 + 130 * twk))
            p.setBrush(c)
            p.drawEllipse(int(bx * w), int(ph * h), int(2 * r), int(2 * r))
        # the green "stonks" up-arrow, bobbing like it's pumping
        bob = math.sin(self._t * 0.07) * 10
        g = QColor("#3ce63c")
        x0, y0 = w * 0.22, h * 0.78 + bob
        x1, y1 = w * 0.74, h * 0.30 + bob
        shaft = QPainterPath()
        shaft.moveTo(x0, y0); shaft.lineTo(x1, y1)
        from PyQt6.QtGui import QPen
        pen = QPen(g); pen.setWidth(max(6, int(min(w, h) * 0.03)))
        p.setPen(pen)
        p.drawLine(int(w * 0.12), int(h * 0.70 + bob), int(x0), int(y0))
        p.drawLine(int(x0), int(y0), int(x1), int(y1))
        p.setPen(Qt.PenStyle.NoPen)
        ah = max(20, int(min(w, h) * 0.07))
        head = QPainterPath()
        head.moveTo(x1 + ah * 0.4, y1 - ah * 0.4)
        head.lineTo(x1 - ah, y1 - ah * 0.1)
        head.lineTo(x1 + ah * 0.1, y1 + ah)
        head.closeSubpath()
        p.fillPath(head, g)
        # a rotating lens-flare glint (the classic meme shine)
        fx, fy = w * 0.30, h * 0.28
        R = max(50, int(min(w, h) * 0.18))
        halo = QRadialGradient(fx, fy, R * 1.3)
        halo.setColorAt(0.0, QColor(255, 255, 255, 170))
        halo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(halo)
        p.drawEllipse(int(fx - R * 1.3), int(fy - R * 1.3),
                      int(R * 2.6), int(R * 2.6))
        p.save()
        p.translate(fx, fy)
        p.rotate(math.degrees(self._t * 0.03))
        self._starburst(p, 0, 0, R, QColor(255, 255, 255, 210), spikes=4)
        p.restore()
        self._scrim(p, "#1a0f06", 70)


class MainWindow(QWidget):
    def __init__(self, icon=None):
        super().__init__()
        self._icon = icon or QIcon()
        self.setWindowTitle("automatic VPN")
        outer = QVBoxLayout(self)
        self._backdrop = _Backdrop(self)   # animated bg for artsy themes

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
        self._apply_backdrop()
        # Guided first setup: if we're on the setup screen and something is
        # missing, proactively open the checklist (with one-click fixes) so
        # the user is walked through the prerequisites.
        QTimer.singleShot(350, self._maybe_guide_first_setup)

    # --- animated backdrop (artsy themes) -------------------------------

    def _apply_backdrop(self):
        theme = (cfgmod.load_config().get("ui") or {}).get("theme", DEFAULT_THEME)
        scene = _THEME_BACKDROP.get(theme)
        # Prefer an animated GIF if the theme declares one AND the file ships;
        # otherwise fall back to the painted scene.
        gif = _gif_path(_THEME_GIF[theme]) if theme in _THEME_GIF else ""
        # Tint the GIF scrim with the theme's own background so the dimmed
        # backdrop matches the rest of the UI (kawaii pink, meme dark warm).
        scrim = (_PALETTES.get(theme) or {}).get("BG", "#000000")
        self._backdrop.set_scene(scene, _PALETTES.get(theme),
                                 gif=gif, scrim_hex=scrim)
        if scene or gif:
            self._backdrop.setGeometry(0, 0, self.width(), self.height())
            self._backdrop.lower()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._backdrop.setGeometry(0, 0, self.width(), self.height())
        self._backdrop.lower()

    def showEvent(self, e):
        super().showEvent(e)
        self._backdrop.setGeometry(0, 0, self.width(), self.height())
        self._backdrop.lower()
        self._backdrop.resume()   # animate only while actually shown

    def hideEvent(self, e):
        super().hideEvent(e)
        self._backdrop.pause()    # hidden to tray → stop animating (0% CPU)

    def changeEvent(self, e):
        super().changeEvent(e)
        # Pause the animated backdrop while minimised; resume when restored.
        from PyQt6.QtCore import QEvent
        if e.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self._backdrop.pause()
            else:
                self._backdrop.resume()

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
        global _CURRENT_ACCENT, _CURRENT_THEME
        ui = cfgmod.load_config().get("ui") or {}
        _CURRENT_ACCENT = ui.get("accent", DEFAULT_ACCENT)
        _CURRENT_THEME = ui.get("theme", DEFAULT_THEME)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_build_stylesheet(_CURRENT_ACCENT, _CURRENT_THEME))
        self._rebuild_views("settings")
        self._apply_backdrop()

    def _route(self):
        view = gl.choose_view(cfgmod.load_config(), tw.is_registered())
        self.stack.setCurrentWidget(self.setup if view == "setup" else self.control)

    def _maybe_guide_first_setup(self):
        # Prerequisites are now shown inline in the setup form (PrereqPanel),
        # so a new user already sees what's missing + the install buttons in
        # one place — no separate dialog needs to pop up here anymore.
        return

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
    """Version string for the About box. Prefer the in-source ``__version__``
    — it's the single source of truth and is always correct, both in a dev
    checkout and in the frozen exe. Installed-package metadata is only a last
    resort: an editable install (or a stale build venv) keeps the version it
    was first installed at, which would show an outdated number here."""
    try:
        import automatic_openconnect
        return automatic_openconnect.__version__
    except Exception:
        try:
            from importlib.metadata import version
            return version("automatic-openconnect")
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
    global _CURRENT_ACCENT, _CURRENT_THEME
    ui = (cfgmod.load_config().get("ui") or {})
    # Pick up the saved UI language (default English) before building widgets.
    i18n.set_lang(ui.get("lang", "en"))
    _CURRENT_ACCENT = ui.get("accent", DEFAULT_ACCENT)
    _CURRENT_THEME = ui.get("theme", DEFAULT_THEME)
    app = QApplication(sys.argv)
    _load_bundled_fonts()   # register the bundled pixel font etc.
    app.setStyleSheet(_build_stylesheet(_CURRENT_ACCENT, _CURRENT_THEME))
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
