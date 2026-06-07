# scripts/theme_smoke.py
# -*- coding: utf-8 -*-
"""Offscreen smoke test for the GUI themes / animated backdrops.

Run with an offscreen Qt platform so it works headless / in CI:

    QT_QPA_PLATFORM=offscreen python scripts/theme_smoke.py        # bash
    $env:QT_QPA_PLATFORM='offscreen'; python scripts\theme_smoke.py  # PowerShell

It asserts that:
  * _build_stylesheet(...) for every theme leaves NO @TOKEN@ unsubstituted;
  * a _Backdrop can be constructed, resized, and every _scene_* paints onto a
    QPixmap without raising.
"""
from __future__ import annotations

import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from automatic_openconnect import gui  # noqa: E402

_TOKEN = re.compile(r"@[A-Z_]+@")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    gui._load_bundled_fonts()

    # 1) Every theme builds a fully-substituted stylesheet (no leftover tokens).
    for th in gui._PALETTES:
        qss = gui._build_stylesheet("blue", th)
        leftover = _TOKEN.findall(qss)
        assert not leftover, f"theme {th!r} has leftover tokens: {leftover}"
    print(f"OK: {len(gui._PALETTES)} themes, no leftover tokens")

    # 2) Every backdrop scene paints without raising.
    host = QWidget()
    bd = gui._Backdrop(host)
    bd.resize(640, 560)
    scenes = sorted({s for s in gui._THEME_BACKDROP.values()})
    for scene in scenes:
        bd._scene = scene
        bd._pal = {}
        for t_val in (0.0, 37.0, 250.0):   # a few animation frames
            bd._t = t_val
            pm = QPixmap(bd.size())
            pm.fill()
            p = QPainter(pm)
            try:
                getattr(bd, f"_scene_{scene}")(p)
            finally:
                p.end()
    print(f"OK: {len(scenes)} scenes painted: {', '.join(scenes)}")

    # 3) Every backdrop theme maps to a real scene method.
    for th, scene in gui._THEME_BACKDROP.items():
        assert hasattr(bd, f"_scene_{scene}"), f"{th}: missing _scene_{scene}"
    # 4) Pixel theme is fully wired.
    assert "pixel" in gui._PALETTES
    assert "pixel" in gui._THEME_ACCENTS
    assert gui._THEME_BACKDROP.get("pixel") == "pixels"
    assert "pixel" in gui._SQUARE_THEMES
    print("OK: pixel theme fully wired")

    print("ALL THEME SMOKE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
