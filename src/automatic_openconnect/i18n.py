# src/automatic_openconnect/i18n.py
# -*- coding: utf-8 -*-
"""Tiny dict-based translations. English is the default; German is
selectable. Qt-free so it can be used from any module and unit-tested.

Other modules return stable KEYS (e.g. "step.signing_in"); only the GUI
renders them via :func:`t`. To add a language, add a column to ``_STRINGS``.
"""

from __future__ import annotations

DEFAULT_LANG = "en"
LANGUAGES = {"en": "English", "de": "Deutsch"}

_lang = DEFAULT_LANG

# key -> {lang: text}.  "automatic VPN" (brand) is intentionally not translated.
_STRINGS: dict[str, dict[str, str]] = {
    # control view
    "app.subtitle": {
        "en": "Connect to your VPN — no password or 2FA typing",
        "de": "VPN verbinden — ohne Passwort & 2FA tippen"},
    "btn.connect": {"en": "Connect", "de": "Verbinden"},
    "btn.disconnect": {"en": "Disconnect", "de": "Trennen"},
    "btn.show_log": {"en": "Show log", "de": "Log anzeigen"},
    "btn.check_prereqs": {"en": "Check prerequisites",
                          "de": "Voraussetzungen prüfen"},
    "btn.reconfigure": {"en": "Configuration…", "de": "Konfiguration…"},
    "btn.report_bug": {"en": "Report a bug", "de": "Fehler melden"},
    "btn.back": {"en": "Back", "de": "Zurück"},
    "status.connected": {"en": "Connected", "de": "Verbunden"},
    "status.disconnected": {"en": "Disconnected", "de": "Getrennt"},
    "status.failed_log": {"en": "Connection failed — “Show log”",
                          "de": "Verbindung fehlgeschlagen — „Log anzeigen“"},
    "status.timeout_log": {"en": "Timed out — “Show log”",
                           "de": "Zeitüberschreitung — „Log anzeigen“"},
    # connect steps
    "step.connecting": {"en": "Connecting …", "de": "Verbinde …"},
    "step.preparing": {"en": "Preparing …", "de": "Vorbereitung …"},
    "step.signing_in": {"en": "Signing in …", "de": "Anmeldung läuft …"},
    "step.tunnel": {"en": "Bringing tunnel up …",
                    "de": "Tunnel wird aufgebaut …"},
    "step.almost": {"en": "Almost done …", "de": "Fast fertig …"},
    "step.failed": {"en": "Connection failed",
                    "de": "Verbindung fehlgeschlagen"},
    # setup view
    "setup.email": {"en": "Email", "de": "E-Mail"},
    "setup.server": {"en": "Server", "de": "Server"},
    "setup.password": {"en": "Password", "de": "Passwort"},
    "setup.totp": {"en": "TOTP seed", "de": "TOTP-Seed"},
    "setup.pw_ph": {"en": "your login password",
                    "de": "dein Login-Passwort"},
    "setup.totp_ph": {"en": "base32 seed (or import from a QR image below)",
                      "de": "base32-Seed (oder unten per QR-Bild importieren)"},
    "setup.stop_conflicting": {
        "en": "Stop conflicting VPN services while connecting",
        "de": "Konkurrierende VPN-Dienste beim Verbinden stoppen"},
    "setup.services": {"en": "Services to stop",
                       "de": "Zu stoppende Dienste"},
    "setup.services_ph": {
        "en": "comma-separated Windows service names",
        "de": "kommagetrennte Windows-Dienstnamen"},
    "setup.load_qr": {"en": "Load QR-code image…",
                      "de": "QR-Code-Bild laden…"},
    "setup.totp_help_btn": {"en": "How do I get the seed?",
                            "de": "Wie bekomme ich den Seed?"},
    "setup.totp_hotkey": {
        "en": "Type the current 2FA code into any field with {combo}",
        "de": "Aktuellen 2FA-Code per {combo} in jedes Feld eintippen"},
    "setup.submit": {"en": "Set up (one-time admin prompt)",
                     "de": "Einrichten (einmaliger Admin-Dialog)"},
    "setup.save": {"en": "Save changes", "de": "Änderungen speichern"},
    "setup.fix_errors": {"en": "Please fix", "de": "Bitte korrigieren"},
    "setup.failed": {"en": "Setup failed", "de": "Setup fehlgeschlagen"},
    "setup.done_title": {"en": "Done", "de": "Fertig"},
    "setup.done_msg": {
        "en": "Set up. Connecting no longer needs an admin prompt.",
        "de": "Eingerichtet. Verbinden braucht jetzt keinen Admin-Dialog mehr."},
    "setup.saved_msg": {
        "en": "Changes saved.",
        "de": "Änderungen gespeichert."},
    # validation errors
    "err.email_empty": {"en": "Email must not be empty.",
                        "de": "E-Mail darf nicht leer sein."},
    "err.server_empty": {"en": "Server must not be empty.",
                         "de": "Server darf nicht leer sein."},
    "err.openconnect_missing": {
        "en": "openconnect.exe was not found at the given path.",
        "de": "openconnect.exe wurde unter dem angegebenen Pfad nicht gefunden."},
    "err.sso_missing": {
        "en": "openconnect-sso was not found at the given path.",
        "de": "openconnect-sso wurde unter dem angegebenen Pfad nicht gefunden."},
    # QR / TOTP
    "qr.unavailable_title": {"en": "QR detection unavailable",
                             "de": "QR-Erkennung nicht verfügbar"},
    "qr.unavailable_msg": {
        "en": "QR detection needs OpenCV. Reinstall with:\n"
              "  uv tool install --reinstall --with opencv-python-headless "
              "--with PyQt6 --with \"setuptools<70\" automatic-openconnect\n"
              "Or enter the base32 seed manually.",
        "de": "QR-Erkennung benötigt OpenCV. Neu installieren mit:\n"
              "  uv tool install --reinstall --with opencv-python-headless "
              "--with PyQt6 --with \"setuptools<70\" automatic-openconnect\n"
              "Oder den base32-Seed manuell eintragen."},
    "qr.read_error": {"en": "Could not read image", "de": "Fehler beim Lesen"},
    "qr.found_title": {"en": "Seed detected", "de": "Seed erkannt"},
    "qr.found_msg": {
        "en": "TOTP seed taken from the QR code. Save with “Set up”.",
        "de": "TOTP-Seed aus dem QR-Code übernommen. Mit „Einrichten“ speichern."},
    "qr.none_title": {"en": "No seed found", "de": "Kein Seed gefunden"},
    "qr.none_msg": {
        "en": "No TOTP QR code was detected in the image. Use a sharp, "
              "complete picture of the QR code.",
        "de": "Im Bild wurde kein TOTP-QR-Code erkannt. Achte auf ein "
              "scharfes, vollständiges Bild des QR-Codes."},
    "qr.pick_title": {"en": "Choose QR-code image",
                      "de": "QR-Code-Bild wählen"},
    "totp.help_title": {"en": "Find your TOTP seed",
                        "de": "TOTP-Seed finden"},
    "totp.help_text": {
        "en": ("The TOTP seed is NOT the 6-digit code, but the long base32 "
               "key behind the QR code.\n\n"
               "How to get it:\n"
               "1. In your account / identity-provider portal, open the "
               "two-factor / authenticator setup and add a new authenticator "
               "app.\n"
               "2. A QR code appears. Click “Unable to scan?” — the long "
               "key shown (base32) is your seed.\n"
               "3. Either paste that key into the “TOTP seed” field, or "
               "upload a screenshot/photo of the QR code with “Load "
               "QR-code image…” — the app reads the seed automatically.\n\n"
               "Note: the seed is usually shown only ONCE. If you no longer "
               "have it, register a new authenticator app to get a new "
               "QR code / seed."),
        "de": ("Der TOTP-Seed ist NICHT der 6-stellige Code, sondern der "
               "lange Base32-Schlüssel hinter dem QR-Code.\n\n"
               "So bekommst du ihn:\n"
               "1. Im Account-/Identity-Provider-Portal die Zwei-Faktor-/"
               "Authenticator-Einrichtung öffnen und eine neue Authenticator-"
               "App hinzufügen.\n"
               "2. Es erscheint ein QR-Code. Klick auf „Barcode nicht "
               "scannen?“ — der lange Schlüssel (Base32) ist dein Seed.\n"
               "3. Entweder den Schlüssel ins Feld „TOTP-Seed“ eintragen, "
               "ODER einen Screenshot/Foto des QR-Codes mit „QR-Code-Bild "
               "laden…“ hochladen — die App liest den Seed automatisch.\n\n"
               "Hinweis: Der Seed wird meist nur EINMAL angezeigt. Hast du "
               "ihn nicht mehr, registriere eine neue Authenticator-App.")},
    # prerequisites checklist
    "check.openconnect": {"en": "openconnect.exe — VPN engine",
                          "de": "openconnect.exe — VPN-Engine"},
    "check.sso": {"en": "openconnect-sso — login",
                  "de": "openconnect-sso — Login"},
    "check.config": {"en": "config.toml — login fields",
                     "de": "config.toml — Login-Felder"},
    "check.credentials": {"en": "Credentials in keyring",
                          "de": "Zugangsdaten im Keyring"},
    "fix.openconnect": {
        "en": "Install openconnect-gui (provides openconnect.exe + Wintun "
              "driver), then enter the path in setup.",
        "de": "openconnect-gui installieren (enthält openconnect.exe + "
              "Wintun-Treiber), dann den Pfad im Setup eintragen."},
    "fix.sso": {"en": "Can be installed automatically via uv.",
                "de": "Kann automatisch per uv installiert werden."},
    "fix.config": {"en": "The login-field template (config.toml) can be "
                         "created automatically.",
                   "de": "Die Login-Felder-Vorlage (config.toml) kann "
                         "automatisch angelegt werden."},
    "fix.credentials_noemail": {
        "en": "Enter your email in setup, then set password + TOTP seed.",
        "de": "E-Mail im Setup eintragen, dann Passwort + TOTP-Seed setzen."},
    "fix.credentials": {
        "en": "Enter password + TOTP seed in setup (stored securely in the "
              "Windows vault).",
        "de": "Passwort + TOTP-Seed im Setup eintragen (sicher im "
              "Windows-Tresor)."},
    "preflight.title": {"en": "Prerequisites", "de": "Voraussetzungen"},
    "preflight.all_ok": {"en": "All set — you can connect.",
                         "de": "Alles bereit — du kannst dich verbinden."},
    "preflight.todo": {"en": "Resolve the open items — the buttons help.",
                       "de": "Erledige die offenen Punkte — die Buttons helfen."},
    "preflight.ok": {"en": "OK", "de": "OK"},
    "preflight.missing": {"en": "MISSING", "de": "FEHLT"},
    "fixbtn.open_download": {"en": "Open download page",
                             "de": "Download-Seite öffnen"},
    "fixbtn.install_sso": {"en": "Install now", "de": "Jetzt installieren"},
    "fixbtn.create_config": {"en": "Create config.toml",
                             "de": "config.toml anlegen"},
    "fixbtn.open_setup": {"en": "Go to setup", "de": "Zum Setup"},
    "config.created_title": {"en": "Created", "de": "Angelegt"},
    "config.created_msg": {"en": "config.toml created:", "de": "config.toml angelegt:"},
    "sso.installing": {"en": "Installing openconnect-sso … (1–2 minutes)",
                       "de": "openconnect-sso wird installiert … (1–2 Minuten)"},
    "sso.install_title": {"en": "Installation", "de": "Installation"},
    "sso.install_ok": {"en": "openconnect-sso was installed.",
                       "de": "openconnect-sso wurde installiert."},
    "sso.install_fail": {"en": "Installation failed (exit %s).",
                         "de": "Installation fehlgeschlagen (Exit %s)."},
    "sso.no_uv": {
        "en": "uv not found. Please install uv or set up openconnect-sso "
              "manually.",
        "de": "uv nicht gefunden. Bitte uv installieren oder openconnect-sso "
              "manuell einrichten."},
    # log dialog
    "log.title": {"en": "Connection log", "de": "Verbindungs-Log"},
    "log.empty": {"en": "No connection log yet.",
                  "de": "Noch kein Verbindungs-Log vorhanden."},
    # tray
    "tray.open": {"en": "Open", "de": "Öffnen"},
    "tray.quit": {"en": "Quit", "de": "Beenden"},
    "tray.tip_connected": {"en": "Connected", "de": "Verbunden"},
    "tray.tip_connecting": {"en": "Connecting …", "de": "Verbinde …"},
    "tray.tip_error": {"en": "Error — see log", "de": "Fehler — Log ansehen"},
    "tray.tip_disconnected": {"en": "Disconnected", "de": "Getrennt"},
    "tray.minimized": {
        "en": "Still running — control it from the tray icon.",
        "de": "Läuft im Hintergrund weiter — über das Tray-Icon steuern."},
    # close dialog
    "close.title": {"en": "automatic VPN", "de": "automatic VPN"},
    "close.text": {"en": "The VPN tunnel is still connected.",
                   "de": "Der VPN-Tunnel ist noch verbunden."},
    "close.info": {"en": "Disconnect or keep running in the background?",
                   "de": "Verbindung trennen oder im Hintergrund weiterlaufen "
                         "lassen?"},
    "close.disconnect": {"en": "Disconnect", "de": "Trennen"},
    "close.background": {"en": "Keep in background",
                         "de": "Im Hintergrund lassen"},
    "close.cancel": {"en": "Cancel", "de": "Abbrechen"},
    "close.dont_ask": {"en": "Don't show this again",
                       "de": "Diese Abfrage nicht mehr anzeigen"},
    # show/hide secrets (eye icon tooltips)
    "btn.show": {"en": "Show", "de": "Anzeigen"},
    "btn.hide": {"en": "Hide", "de": "Verbergen"},
    # app settings
    "settings.title": {"en": "Settings", "de": "Einstellungen"},
    "settings.sec_startup": {"en": "Startup & tray",
                             "de": "Start & Tray"},
    "settings.autostart": {"en": "Start automatically at login",
                           "de": "Beim Anmelden automatisch starten"},
    "settings.start_minimized": {"en": "Start minimised to the tray",
                                 "de": "Minimiert im Tray starten"},
    "settings.notifications": {"en": "Show tray notifications",
                               "de": "Tray-Benachrichtigungen anzeigen"},
    "settings.sec_appearance": {"en": "Appearance", "de": "Darstellung"},
    "settings.theme": {"en": "Theme", "de": "Design"},
    "settings.theme_dark": {"en": "Dark", "de": "Dunkel"},
    "settings.theme_light": {"en": "Light", "de": "Hell"},
    "settings.accent": {"en": "Accent colour", "de": "Akzentfarbe"},
    "settings.sec_status": {"en": "Status colours", "de": "Statusfarben"},
    "settings.state_connected": {"en": "Connected", "de": "Verbunden"},
    "settings.state_connecting": {"en": "Connecting", "de": "Verbindet"},
    "settings.state_disconnected": {"en": "Disconnected", "de": "Getrennt"},
    "settings.state_error": {"en": "Error", "de": "Fehler"},
    "settings.pick_color": {"en": "Pick a colour", "de": "Farbe wählen"},
    "settings.sec_behaviour": {"en": "Behaviour", "de": "Verhalten"},
    "settings.on_exit": {"en": "On exit (connected)",
                         "de": "Beim Beenden (verbunden)"},
    "settings.exit_ask": {"en": "Ask", "de": "Nachfragen"},
    "settings.exit_disconnect": {"en": "Disconnect", "de": "Trennen"},
    "settings.exit_background": {"en": "Keep connected in background",
                                 "de": "Im Hintergrund verbunden lassen"},
    "settings.sec_maintenance": {"en": "Maintenance", "de": "Wartung"},
    "settings.open_config": {"en": "Open config folder",
                             "de": "Konfigurationsordner öffnen"},
    "settings.open_log": {"en": "Open log file", "de": "Log-Datei öffnen"},
    "settings.sec_about": {"en": "About & legal", "de": "Über & Rechtliches"},
    "settings.disclaimer": {
        "en": "Community tool — not affiliated with or supported by the "
              "University of Graz or uniIT. Provided as is, use at your own risk.",
        "de": "Community-Tool — nicht von der Universität Graz oder uniIT "
              "betreut oder unterstützt. Ohne Gewähr, Nutzung auf eigene Gefahr."},
    "settings.license": {
        "en": "Licensed under the MIT License. © 2026 saiko-psych.",
        "de": "Lizenziert unter der MIT-Lizenz. © 2026 saiko-psych."},
    "settings.open_repo": {"en": "Open repository", "de": "Repository öffnen"},
    "settings.third_party": {"en": "Third-party licenses",
                             "de": "Drittanbieter-Lizenzen"},
    "settings.third_party_text": {
        "en": "automatic VPN is open source (MIT) and builds on these "
              "components, each under its own open-source license:\n\n"
              "• openconnect-sso\n• OpenConnect\n• Qt / PyQt6\n• pyotp\n"
              "• pynput\n• keyring\n• OpenCV (optional — QR import)\n\n"
              "See each project's repository for the full license terms.",
        "de": "automatic VPN ist quelloffen (MIT) und baut auf diesen "
              "Komponenten auf, jede unter ihrer eigenen Open-Source-Lizenz:\n\n"
              "• openconnect-sso\n• OpenConnect\n• Qt / PyQt6\n• pyotp\n"
              "• pynput\n• keyring\n• OpenCV (optional — QR-Import)\n\n"
              "Die vollständigen Lizenzbedingungen findest du im jeweiligen Projekt."},
    "tray.started_hidden": {"en": "Running in the tray.",
                            "de": "Läuft im Tray."},
    # generic
    "generic.error": {"en": "Error", "de": "Fehler"},
    "lang.label": {"en": "Language", "de": "Sprache"},
}


def set_lang(code: str) -> None:
    global _lang
    _lang = code if code in LANGUAGES else DEFAULT_LANG


def get_lang() -> str:
    return _lang


def t(key: str, lang: str = None) -> str:
    """Translate a key into the given (or current) language. Falls back to
    English, then to the key itself."""
    code = lang or _lang
    entry = _STRINGS.get(key)
    if not entry:
        return key
    return entry.get(code) or entry.get(DEFAULT_LANG) or key
