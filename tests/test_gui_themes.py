# tests/test_gui_themes.py
# -*- coding: utf-8 -*-
"""Smoke tests for the GUI themes and animated backdrops.

These don't assert on pixels (a human reviews the look) — they guard the
mechanics: every theme builds a fully-substituted stylesheet, every theme is
wired into the Settings dropdown / palette / accent maps, and every backdrop
scene paints onto a pixmap without raising. Skipped if PyQt6 isn't installed.
"""

import os
import re
import unittest

# A windowless Qt platform so the suite runs headless / in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PyQt6  # noqa: F401
    _HAVE_PYQT = True
except Exception:  # PyQt6 genuinely not installed -> skip cleanly
    _HAVE_PYQT = False

_IMPORT_ERR = None
try:
    from PyQt6.QtGui import QPainter, QPixmap
    from PyQt6.QtWidgets import QApplication, QWidget
    from automatic_openconnect import gui
    _HAVE_QT = True
except Exception as _exc:  # pragma: no cover - depends on optional GUI deps
    _HAVE_QT = False
    _IMPORT_ERR = repr(_exc)

_TOKEN = re.compile(r"@[A-Z_]+@")


class TestGuiImportDiagnostic(unittest.TestCase):
    def test_gui_imports_when_pyqt_present(self):
        # If PyQt6 is installed, importing the gui module must succeed —
        # otherwise the theme smoke tests would silently skip on a broken
        # module. On a machine without PyQt6 this is a no-op.
        if _HAVE_PYQT:
            self.assertTrue(_HAVE_QT,
                            f"gui import failed despite PyQt6: {_IMPORT_ERR}")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not available")
class TestGuiThemes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        gui._load_bundled_fonts()

    def test_every_theme_stylesheet_fully_substituted(self):
        self.assertTrue(gui._PALETTES)
        for th in gui._PALETTES:
            qss = gui._build_stylesheet("blue", th)
            leftover = _TOKEN.findall(qss)
            self.assertFalse(leftover, f"theme {th!r} leftover tokens: {leftover}")

    def test_every_palette_has_required_keys(self):
        required = {"BG", "FG", "SUB", "HEADER", "PANEL", "BORDER", "HOVER",
                    "DISFG", "DISBG", "INDBORDER", "POPUPSEL", "LOGBG",
                    "FONT", "PRIMARY_FG"}
        for th, pal in gui._PALETTES.items():
            missing = required - set(pal)
            self.assertFalse(missing, f"theme {th!r} missing keys: {missing}")

    def test_settings_theme_keys_cover_palettes_and_have_i18n(self):
        from automatic_openconnect import i18n
        keys = ["dark", "light", "nord", "plum", "solarized", "sand",
                "terminal", "y2k", "kawaii", "vaporwave", "pixel"]
        # Every dropdown key is a real palette and has a translation.
        for k in keys:
            self.assertIn(k, gui._PALETTES, f"{k} not in _PALETTES")
            label = i18n.t(f"settings.theme_{k}")
            self.assertNotEqual(label, f"settings.theme_{k}",
                                f"missing i18n for {k}")

    def test_pixel_theme_fully_wired(self):
        self.assertIn("pixel", gui._PALETTES)
        self.assertIn("pixel", gui._THEME_ACCENTS)
        self.assertIn("pixel", gui._SQUARE_THEMES)
        self.assertEqual(gui._THEME_BACKDROP.get("pixel"), "pixels")
        self.assertEqual(gui._PALETTES["pixel"]["FONT"], gui._PIXEL)

    def test_backdrop_map_points_at_real_scene_methods(self):
        host = QWidget()
        bd = gui._Backdrop(host)
        for theme, scene in gui._THEME_BACKDROP.items():
            self.assertTrue(hasattr(bd, f"_scene_{scene}"),
                            f"{theme}: missing _scene_{scene}")

    def test_all_scenes_paint_without_error(self):
        host = QWidget()
        bd = gui._Backdrop(host)
        bd.resize(640, 560)
        scenes = sorted(set(gui._THEME_BACKDROP.values()))
        self.assertTrue(scenes)
        for scene in scenes:
            bd._scene = scene
            bd._pal = {}
            for t_val in (0.0, 37.0, 250.0):     # a few animation frames
                bd._t = t_val
                pm = QPixmap(bd.size())
                pm.fill()
                p = QPainter(pm)
                try:
                    getattr(bd, f"_scene_{scene}")(p)
                finally:
                    p.end()


if __name__ == "__main__":
    unittest.main()
