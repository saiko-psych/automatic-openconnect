# tests/test_tasks_windows.py
# -*- coding: utf-8 -*-
"""Tests for automatic_openconnect.tasks_windows.

All subprocess calls are mocked; no real tasks are registered and no
elevation occurs. Verifies command construction and the grant-once flow.
"""

import base64
import subprocess
import unittest
from unittest import mock

from automatic_openconnect import tasks_windows as tw
from automatic_openconnect.core import VPNError


class TestBuilders(unittest.TestCase):
    def test_register_script_names_both_tasks(self):
        script = tw.build_register_script(r"C:\py\python.exe",
                                          r"C:\Users\x\AppData\Roaming\automatic-openconnect\config.json")
        self.assertIn(tw.TASK_UP, script)
        self.assertIn(tw.TASK_DOWN, script)

    def test_register_script_requests_highest_privileges(self):
        script = tw.build_register_script("py", "cfg")
        self.assertIn("Highest", script)

    def test_register_script_targets_windows_backend_with_config(self):
        script = tw.build_register_script(r"C:\py.exe", r"C:\cfg.json")
        self.assertIn("automatic_openconnect._windows", script)
        self.assertIn("up", script)
        self.assertIn("down", script)
        self.assertIn(r"C:\cfg.json", script)

    def test_elevated_launch_uses_runas_and_encodedcommand(self):
        argv = tw.build_elevated_launch("Write-Host hi")
        joined = " ".join(argv)
        self.assertIn("Start-Process", joined)
        self.assertIn("RunAs", joined)
        self.assertIn("EncodedCommand", joined)

    def test_elevated_launch_encodes_script_as_utf16le_base64(self):
        import re
        inner = "Write-Host hi"
        argv = tw.build_elevated_launch(inner)
        cmd = argv[-1]
        m = re.search(r"'-EncodedCommand','([A-Za-z0-9+/=]+)'", cmd)
        self.assertIsNotNone(m)
        decoded = base64.b64decode(m.group(1)).decode("utf-16-le")
        self.assertEqual(decoded, inner)


class TestRun(unittest.TestCase):
    def test_run_invokes_schtasks_run(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            tw.run(tw.TASK_UP)
            args = run.call_args[0][0]
            self.assertEqual(args[:3], ["schtasks", "/run", "/tn"])
            self.assertIn(tw.TASK_UP, args)

    def test_run_raises_vpnerror_on_nonzero(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "boom")
            with self.assertRaises(VPNError):
                tw.run(tw.TASK_DOWN)


class TestIsRegistered(unittest.TestCase):
    def test_true_when_query_succeeds(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            self.assertTrue(tw.is_registered())

    def test_false_when_query_fails(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "")
            self.assertFalse(tw.is_registered())


class TestRegister(unittest.TestCase):
    def test_register_launches_elevated_powershell(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            tw.register(r"C:\py.exe", r"C:\cfg.json")
            argv = run.call_args[0][0]
            self.assertEqual(argv[0].lower(), "powershell")
            self.assertIn("Start-Process", " ".join(argv))
