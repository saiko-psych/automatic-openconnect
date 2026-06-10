# tests/test_headless.py
# -*- coding: utf-8 -*-
"""Headless guarantees (issue #5 + the headless CLI).

The package advertises a headless library + a Linux `up/down/status` CLI for
servers. Both MUST work without the desktop stack (PyQt6 / pynput). These run in
a FRESH subprocess so an already-imported PyQt6 (from the GUI tests) can't mask a
regression — if someone adds a top-level `import PyQt6` to a library module,
these fail.
"""

import subprocess
import sys


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True)


def test_library_import_pulls_no_desktop_stack():
    r = _run(
        "import sys, automatic_openconnect as a\n"
        "ctx = a.auto_vpn_session({'auto_vpn': {'enabled': False}})\n"
        "ctx.__enter__(); ctx.__exit__(None, None, None)\n"
        "assert 'PyQt6' not in sys.modules, 'PyQt6 leaked into the library path'\n"
        "assert not any(m.startswith('pynput') for m in sys.modules), 'pynput leaked'\n"
        "print('OK')\n"
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_headless_cli_status_pulls_no_desktop_stack():
    r = _run(
        "import sys\n"
        "sys.argv = ['automatic_openconnect', 'status']\n"
        "from automatic_openconnect._linux import main_cli\n"
        "rc = main_cli()\n"
        "assert 'PyQt6' not in sys.modules, 'PyQt6 leaked into the headless CLI'\n"
        "assert not any(m.startswith('pynput') for m in sys.modules), 'pynput leaked'\n"
        "print('OK', rc)\n"
    )
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout
