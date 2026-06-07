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

    def test_register_script_runs_python_directly_no_cmd_wrapper(self):
        # Regression: the task must run python.exe directly. A cmd.exe
        # wrapper mangled the --config path via nested quote-stripping, and
        # `& pause` masked python's real exit code (the failed `up` looked
        # like success). No cmd, no pause, no backslash-escaped quotes.
        script = tw.build_register_script(r"C:\py\python.exe", r"C:\cfg.json")
        self.assertNotIn('\\"', script)          # no backslash-escaped quotes
        self.assertNotIn("cmd.exe", script)      # no cmd wrapper
        self.assertNotIn("pause", script)        # no exit-code-masking pause
        # windowless interpreter so no console window pops up
        self.assertIn(r"-Execute 'C:\py\pythonw.exe'", script)
        self.assertNotIn(r"'C:\py\python.exe'", script)
        self.assertIn('--config "C:\\cfg.json"', script)

    def test_register_script_frozen_runs_exe_directly(self):
        # Frozen (PyInstaller) build: the task runs the app exe with the
        # up/down subcommand — no python, no `-m module`.
        script = tw.build_register_script(
            r"C:\app\automatic-vpn.exe", r"C:\cfg.json", frozen=True)
        self.assertNotIn('\\"', script)
        self.assertNotIn("-m automatic_openconnect", script)
        self.assertNotIn("pythonw", script)
        self.assertIn(r"-Execute 'C:\app\automatic-vpn.exe'", script)
        self.assertIn('up --config "C:\\cfg.json"', script)
        self.assertIn('down --config "C:\\cfg.json"', script)

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
        cmd = argv[argv.index("-Command") + 1]
        m = re.search(r"'-EncodedCommand','([A-Za-z0-9+/=]+)'", cmd)
        self.assertIsNotNone(m)
        decoded = base64.b64decode(m.group(1)).decode("utf-16-le")
        self.assertEqual(decoded, inner)


class TestRun(unittest.TestCase):
    def test_run_invokes_schtasks_run(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            tw.run(tw.TASK_UP)
            args = run.call_args[0][0]
            self.assertEqual(args[:3], ["schtasks", "/run", "/tn"])
            self.assertIn(tw.TASK_UP, args)

    def test_run_raises_vpnerror_on_nonzero(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "boom")
            with self.assertRaises(VPNError):
                tw.run(tw.TASK_DOWN)


class TestEnd(unittest.TestCase):
    def test_end_invokes_schtasks_end(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            tw.end(tw.TASK_UP)
            args = run.call_args[0][0]
            self.assertEqual(args[:3], ["schtasks", "/end", "/tn"])
            self.assertIn(tw.TASK_UP, args)

    def test_end_swallows_missing_schtasks(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run",
                        side_effect=FileNotFoundError()):
            tw.end(tw.TASK_UP)  # must not raise


class TestIsRegistered(unittest.TestCase):
    def test_true_when_query_succeeds(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            self.assertTrue(tw.is_registered())

    def test_false_when_query_fails(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "")
            self.assertFalse(tw.is_registered())


class TestRegister(unittest.TestCase):
    def test_register_launches_elevated_powershell(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            tw.register(r"C:\py.exe", r"C:\cfg.json")
            argv = run.call_args[0][0]
            self.assertEqual(argv[0].lower(), "powershell")
            self.assertIn("Start-Process", " ".join(argv))

    def test_register_raises_vpnerror_on_nonzero(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "cancelled")
            with self.assertRaises(VPNError):
                tw.register(r"C:\py.exe", r"C:\cfg.json")


class TestParseLastResult(unittest.TestCase):
    """Parsing the 'Last Result' code out of `schtasks /query /v /fo LIST`."""

    def test_english_decimal(self):
        out = ("TaskName: \\AutoOpenconnect-Up\n"
               "Status: Ready\n"
               "Last Result: 1\n")
        self.assertEqual(tw.parse_last_result(out), 1)

    def test_english_hex(self):
        out = "Last Result: 0x80070002\n"
        self.assertEqual(tw.parse_last_result(out), 0x80070002)

    def test_german_label(self):
        out = "Letztes Ergebnis: 267009\n"
        self.assertEqual(tw.parse_last_result(out), tw.TASK_STILL_RUNNING)

    def test_success_zero(self):
        self.assertEqual(tw.parse_last_result("Last Result: 0\n"), 0)

    def test_missing_returns_none(self):
        self.assertIsNone(tw.parse_last_result("Status: Ready\n"))

    def test_unparsable_value_returns_none(self):
        self.assertIsNone(tw.parse_last_result("Last Result: N/A\n"))


class TestLastRunResult(unittest.TestCase):
    def test_queries_schtasks_verbose_list(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                [], 0, "Last Result: 0\n", "")
            self.assertEqual(tw.last_run_result(tw.TASK_UP), 0)
            args = run.call_args[0][0]
            self.assertEqual(args[:3], ["schtasks", "/query", "/tn"])
            self.assertIn("/v", args)
            self.assertIn("LIST", args)

    def test_none_when_query_fails(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "")
            self.assertIsNone(tw.last_run_result(tw.TASK_UP))

    def test_none_when_schtasks_missing(self):
        with mock.patch("automatic_openconnect.tasks_windows.subprocess.run",
                        side_effect=FileNotFoundError()):
            self.assertIsNone(tw.last_run_result(tw.TASK_UP))


class TestDescribeLastResult(unittest.TestCase):
    def test_none(self):
        self.assertIn("could not read", tw.describe_last_result(None).lower())

    def test_zero_is_success(self):
        self.assertIn("success", tw.describe_last_result(0).lower())

    def test_still_running(self):
        self.assertIn("still running",
                      tw.describe_last_result(tw.TASK_STILL_RUNNING).lower())

    def test_failure_shows_hex_code(self):
        msg = tw.describe_last_result(0x80070002)
        self.assertIn("0x80070002", msg)
        self.assertIn("failed", msg.lower())
