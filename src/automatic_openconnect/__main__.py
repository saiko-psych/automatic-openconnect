# src/automatic_openconnect/__main__.py
# -*- coding: utf-8 -*-
"""``python -m automatic_openconnect`` entry point — platform-aware.

- **Windows:** the full GUI app (and the ``up``/``down``/``status`` backend the
  elevated Scheduled Task runs) via ``gui.run()``. Importing ``gui`` pulls in the
  Windows scheduled-task machinery, so we only do that on Windows.
- **Linux / macOS:** the lean system-tray app (``_posix_tray``). There
  openconnect-sso does the SAML auth AND launches openconnect via passwordless
  sudo, so no scheduled-task / grant-once-elevation dance is needed.
"""

import sys


def _main() -> int:
    if sys.platform == "win32":
        from .gui import run
        return run()
    from ._posix_tray import run as posix_run
    return posix_run()


if __name__ == "__main__":
    sys.exit(_main())
