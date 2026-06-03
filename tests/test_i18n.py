# tests/test_i18n.py
# -*- coding: utf-8 -*-
"""Tests for the dict-based translations."""

import unittest

from automatic_openconnect import i18n


class TestI18n(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("en")

    def test_default_is_english(self):
        i18n.set_lang("en")
        self.assertEqual(i18n.t("btn.connect"), "Connect")

    def test_german(self):
        self.assertEqual(i18n.t("btn.connect", "de"), "Verbinden")

    def test_set_lang_switches_current(self):
        i18n.set_lang("de")
        self.assertEqual(i18n.t("btn.disconnect"), "Trennen")

    def test_unknown_key_returns_key(self):
        self.assertEqual(i18n.t("does.not.exist"), "does.not.exist")

    def test_unknown_lang_falls_back_to_default(self):
        i18n.set_lang("zz")
        self.assertEqual(i18n.get_lang(), "en")

    def test_keys_from_pure_modules_have_translations(self):
        keys = [
            "step.connecting", "step.preparing", "step.signing_in",
            "step.tunnel", "step.almost", "step.failed",
            "err.email_empty", "err.server_empty",
            "err.openconnect_missing", "err.sso_missing",
            "check.openconnect", "check.sso", "check.config",
            "check.credentials", "fix.openconnect", "fix.sso", "fix.config",
            "fix.credentials", "fix.credentials_noemail",
        ]
        for k in keys:
            for lang in ("en", "de"):
                self.assertNotEqual(i18n.t(k, lang), k,
                                    f"missing {lang} translation for {k}")
