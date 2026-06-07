# tests/test_autostart.py
# -*- coding: utf-8 -*-
"""Tests for autostart (no winreg / registry access; XDG + LaunchAgent)."""

import os
import tempfile
import unittest
from unittest import mock

from automatic_openconnect import autostart


class TestLaunchCommand(unittest.TestCase):
    def test_frozen_uses_the_exe_itself(self):
        fake_sys = mock.Mock()
        fake_sys.frozen = True
        fake_sys.executable = r"C:\App\automatic-vpn.exe"
        with mock.patch.object(autostart, "sys", fake_sys):
            self.assertEqual(autostart.launch_command(),
                             '"C:\\App\\automatic-vpn.exe"')

    def test_uses_launcher_on_path_when_not_frozen(self):
        fake_sys = mock.Mock()
        fake_sys.frozen = False
        with mock.patch.object(autostart, "sys", fake_sys), \
             mock.patch.object(autostart.shutil, "which",
                               return_value=r"C:\bin\automatic-vpn.exe"):
            self.assertEqual(autostart.launch_command(),
                             '"C:\\bin\\automatic-vpn.exe"')

    def test_dev_fallback_runs_module(self):
        fake_sys = mock.Mock()
        fake_sys.frozen = False
        fake_sys.executable = r"C:\py\python.exe"
        with mock.patch.object(autostart, "sys", fake_sys), \
             mock.patch.object(autostart.shutil, "which", return_value=None), \
             mock.patch.object(autostart.os.path, "exists", return_value=False):
            cmd = autostart.launch_command()
        self.assertIn("-m automatic_openconnect", cmd)
        self.assertIn("python.exe", cmd)


class TestXdgAutostart(unittest.TestCase):
    """Linux: an XDG autostart .desktop entry."""

    def test_desktop_entry_content(self):
        with mock.patch.object(autostart, "launch_argv",
                               return_value=["/usr/bin/automatic-vpn"]):
            entry = autostart._desktop_entry()
        self.assertIn("[Desktop Entry]", entry)
        self.assertIn("Type=Application", entry)
        self.assertIn("Exec=/usr/bin/automatic-vpn", entry)

    def test_enable_disable_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(autostart.sys, "platform", "linux"), \
                 mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": d}), \
                 mock.patch.object(autostart, "launch_argv",
                                   return_value=["/usr/bin/automatic-vpn"]):
                self.assertFalse(autostart.is_enabled())
                autostart.enable()
                self.assertTrue(autostart.is_enabled())
                self.assertTrue(os.path.exists(autostart._desktop_file()))
                autostart.disable()
                self.assertFalse(autostart.is_enabled())


class TestLaunchAgent(unittest.TestCase):
    """macOS: a LaunchAgent plist."""

    def test_plist_content(self):
        argv = ["/Applications/x.app/Contents/MacOS/x"]
        with mock.patch.object(autostart, "launch_argv", return_value=argv):
            plist = autostart._launch_agent_plist()
        self.assertIn("<key>RunAtLoad</key>", plist)
        self.assertIn("<key>ProgramArguments</key>", plist)
        self.assertIn(argv[0], plist)


if __name__ == "__main__":
    unittest.main()
