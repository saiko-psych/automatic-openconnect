# tests/test_autostart.py
# -*- coding: utf-8 -*-
"""Tests for autostart.launch_command (no winreg / registry access)."""

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


if __name__ == "__main__":
    unittest.main()
