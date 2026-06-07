# tests/test_factory.py
# -*- coding: utf-8 -*-
"""Contract tests for the public cross-platform factory.

This is the headless API that Termino (and any caller) integrates with:

    from automatic_openconnect import auto_vpn_session
    with auto_vpn_session(config):
        ...

These tests guard that contract so the ongoing GUI port can't quietly break
it: it must stay importable, dispatch per-OS, and honour the no-op-when-
disabled rule on every platform.
"""

import unittest
from unittest import mock

import automatic_openconnect
from automatic_openconnect import auto_vpn_session, factory


class TestFactoryContract(unittest.TestCase):
    def test_public_api_is_the_cross_platform_factory(self):
        self.assertIs(auto_vpn_session, factory.make_vpn_session)
        self.assertIs(automatic_openconnect.auto_vpn_session,
                      factory.make_vpn_session)
        self.assertTrue(callable(auto_vpn_session))

    def test_noop_when_disabled_on_every_platform(self):
        for plat in ("win32", "linux", "darwin", "freebsd"):
            with mock.patch.object(factory.sys, "platform", plat):
                with auto_vpn_session({"auto_vpn": {"enabled": False}}) as tok:
                    self.assertIsNone(tok, f"should no-op on {plat}")

    def test_unknown_platform_is_noop_even_when_enabled(self):
        with mock.patch.object(factory.sys, "platform", "sunos"):
            cfg = {"auto_vpn": {"enabled": True, "user_email": "x@example.org"}}
            with auto_vpn_session(cfg) as tok:
                self.assertIsNone(tok)

    def test_dispatches_to_the_right_backend_per_os(self):
        cases = [
            ("linux", "_linux", "auto_vpn_session"),
            ("win32", "_windows", "auto_vpn_session_win"),
            ("darwin", "_darwin", "auto_vpn_session"),
        ]
        for plat, module, func in cases:
            with mock.patch.object(factory.sys, "platform", plat), \
                 mock.patch(f"automatic_openconnect.{module}.{func}") as backend:
                backend.return_value = mock.MagicMock()
                factory.make_vpn_session({"auto_vpn": {"enabled": True}})
                backend.assert_called_once()


if __name__ == "__main__":
    unittest.main()
