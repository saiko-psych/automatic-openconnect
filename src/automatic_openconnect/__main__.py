# src/automatic_openconnect/__main__.py
# -*- coding: utf-8 -*-
"""``python -m automatic_openconnect`` entry point — platform-aware.

- **Windows:** the full GUI app (and the ``up``/``down``/``status`` backend the
  elevated Scheduled Task runs) via ``gui.run()``. Importing ``gui`` pulls in the
  Windows scheduled-task machinery, so we only do that on Windows.
- **Linux, ``up``/``down``/``status``:** the **headless CLI** (``_linux.main_cli``)
  — no tray, no Qt, so it runs on a server/container with just the core install.
- **Linux (no args) / macOS:** the lean system-tray app (``_posix_tray``, needs
  the ``[gui]`` extra). There openconnect-sso does the SAML auth AND launches
  openconnect via passwordless sudo — no scheduled-task/elevation dance.
"""

import sys

_HEADLESS_CMDS = ("up", "down", "status")


def _main() -> int:
    if sys.platform == "win32":
        from .gui import run
        return run()
    if (sys.platform == "linux"
            and sys.argv[1:2] and sys.argv[1] in _HEADLESS_CMDS):
        from ._linux import main_cli
        return main_cli()
    from ._posix_tray import run as posix_run
    return posix_run()


if __name__ == "__main__":
    sys.exit(_main())
