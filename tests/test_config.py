# tests/test_config.py
# -*- coding: utf-8 -*-
"""Tests for automatic_openconnect.config (no Qt, no network)."""

import json
import unittest
from pathlib import Path
from unittest import mock

from automatic_openconnect import config as cfgmod


class TestConfigRoundTrip(unittest.TestCase):
    def test_save_then_load_returns_same_data(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = Path(d) / "config.json"
        data = {"auto_vpn": {"enabled": True, "user_email": "x@uni-graz.at",
                             "server": "univpn.uni-graz.at"}}
        cfgmod.save_config(data, path=p)
        self.assertEqual(cfgmod.load_config(path=p), data)

    def test_load_missing_file_returns_empty_dict(self):
        import tempfile
        p = Path(tempfile.mkdtemp()) / "does-not-exist.json"
        self.assertEqual(cfgmod.load_config(path=p), {})

    def test_save_creates_parent_dirs(self):
        import tempfile
        p = Path(tempfile.mkdtemp()) / "nested" / "deep" / "config.json"
        cfgmod.save_config({"a": 1}, path=p)
        self.assertTrue(p.exists())


class TestIsConfigured(unittest.TestCase):
    def test_true_with_email_and_server(self):
        data = {"auto_vpn": {"user_email": "x@uni-graz.at",
                             "server": "univpn.uni-graz.at"}}
        self.assertTrue(cfgmod.is_configured(data))

    def test_false_when_email_missing(self):
        self.assertFalse(cfgmod.is_configured({"auto_vpn": {"server": "s"}}))

    def test_false_on_empty(self):
        self.assertFalse(cfgmod.is_configured({}))


class TestConfigDir(unittest.TestCase):
    def test_uses_programdata_when_set(self):
        # ProgramData (machine-wide) is required so the elevated Scheduled
        # Task can read the same config the GUI wrote — the task cannot see
        # the user's AppData. PROGRAMDATA wins over APPDATA.
        with mock.patch.dict("os.environ",
                             {"PROGRAMDATA": r"C:\ProgramData",
                              "APPDATA": r"C:\Users\x\AppData\Roaming"}):
            self.assertEqual(
                cfgmod.config_dir(),
                Path(r"C:\ProgramData") / "automatic-openconnect",
            )

    def test_falls_back_to_appdata_without_programdata(self):
        with mock.patch.dict("os.environ",
                             {"APPDATA": r"C:\Users\x\AppData\Roaming"},
                             clear=True):
            self.assertEqual(
                cfgmod.config_dir(),
                Path(r"C:\Users\x\AppData\Roaming") / "automatic-openconnect",
            )
