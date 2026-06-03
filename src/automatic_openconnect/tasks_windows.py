# src/automatic_openconnect/tasks_windows.py
# -*- coding: utf-8 -*-
"""Windows Scheduled-Task lifecycle — the grant-once privilege model.

The user elevates ONCE (a single UAC prompt) to register two on-demand
tasks with "Run with highest privileges". Afterwards the GUI fires them
with ``schtasks /run`` — no elevation. This mirrors
``tools/setup-windows-tasks.ps1`` but is driven from Python so the app
needs no external script.

Command construction (``build_*``) is separated from execution so it can
be unit-tested without spawning anything.
"""

from __future__ import annotations

import base64
import subprocess
from typing import List

from .core import VPNError

TASK_UP = "AutoOpenconnect-Up"
TASK_DOWN = "AutoOpenconnect-Down"


def build_register_script(python_exe: str, config_path: str) -> str:
    """Return the PowerShell that registers both tasks (runs elevated).

    Each task runs ``cmd.exe /c "<python> -m automatic_openconnect._windows
    <up|down> --config <cfg> & pause"`` so the elevated console stays open
    to show any VPNError. RunLevel Highest is required for Wintun.
    """
    def task_block(name: str, sub: str) -> str:
        argline = (f'-m automatic_openconnect._windows {sub} '
                   f'--config \\"{config_path}\\"')
        cmdline = f'/c \\"\\"{python_exe}\\" {argline} ^& pause\\"'
        return (
            f"$a = New-ScheduledTaskAction -Execute 'cmd.exe' "
            f"-Argument '{cmdline}';\n"
            f"$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME "
            f"-LogonType Interactive -RunLevel Highest;\n"
            f"$s = New-ScheduledTaskSettingsSet -StartWhenAvailable "
            f"-MultipleInstances IgnoreNew "
            f"-ExecutionTimeLimit (New-TimeSpan -Hours 24);\n"
            f"Register-ScheduledTask -TaskName '{name}' -Action $a "
            f"-Principal $p -Settings $s -Force | Out-Null;\n"
        )

    return task_block(TASK_UP, "up") + task_block(TASK_DOWN, "down")


def build_elevated_launch(inner_script: str) -> List[str]:
    """Wrap a PS script so it runs elevated via one UAC prompt.

    Encodes the inner script as UTF-16LE base64 (PowerShell -EncodedCommand
    convention) to dodge nested-quote hell, then asks the *outer*
    PowerShell to Start-Process an elevated child with -Verb RunAs -Wait.

    The returned argv ends with the quoted base64 token (``'<b64>'``) as a
    discrete element so callers/tests can extract it via
    ``argv[-1].strip("'\"")``.

    When ``subprocess.run`` receives this list on Windows, the CRT
    command-line builder joins the elements with spaces, producing a valid
    single PowerShell statement.
    """
    encoded = base64.b64encode(inner_script.encode("utf-16-le")).decode("ascii")
    # Split the outer PS -Command across multiple argv elements.
    # subprocess on Windows quotes and joins them; PowerShell's -Command
    # then concatenates the remaining args with spaces to form one statement.
    return [
        "powershell", "-NoProfile", "-Command",
        "Start-Process powershell -Verb RunAs -Wait"
        " -ArgumentList '-NoProfile','-EncodedCommand',",
        f"'{encoded}'",
    ]


def register(python_exe: str, config_path: str) -> None:
    """Register both tasks elevated. One UAC prompt. Raises on failure."""
    script = build_register_script(python_exe, config_path)
    argv = build_elevated_launch(script)
    result = subprocess.run(argv, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise VPNError(
            "Task registration failed or was cancelled at the UAC prompt. "
            f"stderr: {(result.stderr or '').strip()[-300:]}"
        )


def unregister() -> None:
    """Remove both tasks elevated (one UAC prompt). Best-effort."""
    script = (f"Unregister-ScheduledTask -TaskName '{TASK_UP}' -Confirm:$false "
              f"-ErrorAction SilentlyContinue;\n"
              f"Unregister-ScheduledTask -TaskName '{TASK_DOWN}' -Confirm:$false "
              f"-ErrorAction SilentlyContinue;\n")
    subprocess.run(build_elevated_launch(script), stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def is_registered() -> bool:
    """True if the Up task exists (proxy for 'setup done'). No elevation."""
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_UP],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0


def run(task: str) -> None:
    """Fire an on-demand task. No elevation. Raises VPNError on failure."""
    result = subprocess.run(
        ["schtasks", "/run", "/tn", task],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise VPNError(
            f"Could not run task {task!r} (exit {result.returncode}). "
            "Is setup complete? "
            f"stderr: {(result.stderr or '').strip()[-300:]}"
        )
