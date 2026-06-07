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
from typing import List, Optional

from .core import VPNError

TASK_UP = "AutoOpenconnect-Up"
TASK_DOWN = "AutoOpenconnect-Down"

# Hide the console window of schtasks/powershell helpers. The GUI runs
# windowless (pythonw.exe), so a console child without this flag would pop
# its own black window. 0 on non-Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def build_register_script(python_exe: str, config_path: str,
                          frozen: bool = False) -> str:
    """Return the PowerShell that registers both tasks (runs elevated).

    Each task runs the executable DIRECTLY — there is deliberately NO
    ``cmd.exe`` wrapper. The previous ``cmd /c "... & pause"`` form was
    doubly broken: nested cmd quote-stripping mangled the ``--config``
    path, and ``& pause`` masked python's real exit code. Task Scheduler
    passes ``-Argument`` straight to the executable, so the quoted config
    path survives into ``sys.argv``. RunLevel Highest is required for Wintun.

    Two modes:
    - ``frozen=True`` (PyInstaller .exe): run the app exe itself with the
      ``up``/``down`` subcommand — ``<app.exe> up --config "<cfg>"``.
    - ``frozen=False`` (dev / uv install): run the windowless interpreter
      with the module — ``pythonw.exe -m automatic_openconnect._windows up
      --config "<cfg>"``. python.exe is swapped for its GUI-subsystem twin
      pythonw.exe so no console window pops up.
    """
    if frozen:
        exe = python_exe
    else:
        exe = python_exe
        if exe.lower().endswith("python.exe"):
            exe = exe[: -len("python.exe")] + "pythonw.exe"

    def task_block(name: str, sub: str) -> str:
        # Registered through a PowerShell SINGLE-quoted -Argument, so the
        # double quotes around the path are stored literally (PowerShell
        # does not process them inside '...'); Windows then hands them to
        # the executable's argv parser.
        if frozen:
            argline = f'{sub} --config "{config_path}"'
        else:
            argline = (f'-m automatic_openconnect._windows {sub} '
                       f'--config "{config_path}"')
        return (
            f"$a = New-ScheduledTaskAction -Execute '{exe}' "
            f"-Argument '{argline}';\n"
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
    The whole Start-Process statement is a single -Command string so
    PowerShell parses it as one statement.
    """
    encoded = base64.b64encode(inner_script.encode("utf-16-le")).decode("ascii")
    inner_args = f"'-NoProfile','-EncodedCommand','{encoded}'"
    outer = (
        f"Start-Process powershell -Verb RunAs -Wait "
        f"-ArgumentList {inner_args}"
    )
    return ["powershell", "-NoProfile", "-Command", outer]


def register(python_exe: str, config_path: str, frozen: bool = False) -> None:
    """Register both tasks elevated. One UAC prompt. Raises on failure."""
    script = build_register_script(python_exe, config_path, frozen)
    argv = build_elevated_launch(script)
    result = subprocess.run(argv, creationflags=_NO_WINDOW,
                            stdin=subprocess.DEVNULL,
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
    subprocess.run(build_elevated_launch(script), creationflags=_NO_WINDOW,
                   stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def is_registered() -> bool:
    """True if the Up task exists (proxy for 'setup done'). No elevation."""
    result = subprocess.run(
        ["schtasks", "/query", "/tn", TASK_UP],
        creationflags=_NO_WINDOW,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0


def end(task: str) -> None:
    """End a running on-demand task instance. No elevation, best-effort.

    The ``up`` task's process blocks forever to hold the tunnel, so its
    instance stays in the "Running" state. With ``MultipleInstances =
    IgnoreNew`` that would prevent the next connect from starting. Ending
    the instance (after the tunnel is already torn down by ``down``) frees
    the slot so a subsequent connect runs fresh. A no-op if not running.
    """
    try:
        subprocess.run(
            ["schtasks", "/end", "/tn", task],
            creationflags=_NO_WINDOW,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def run(task: str) -> None:
    """Fire an on-demand task. No elevation. Raises VPNError on failure."""
    result = subprocess.run(
        ["schtasks", "/run", "/tn", task],
        creationflags=_NO_WINDOW,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise VPNError(
            f"Could not run task {task!r} (exit {result.returncode}). "
            "Is setup complete? "
            f"stderr: {(result.stderr or '').strip()[-300:]}"
        )


# schtasks reports an instance that is still running with this "Last Result"
# code. It is NOT a failure — the up-task is meant to block forever holding
# the tunnel, so this is the expected value while a connect is in progress.
TASK_STILL_RUNNING = 0x41301  # 267009


def parse_last_result(query_output: str) -> Optional[int]:
    """Parse the task's last-run exit code from ``schtasks /query /v /fo LIST``.

    Returns the integer code, or ``None`` if the line could not be found /
    parsed. Handles both the English ("Last Result") and German ("Letztes
    Ergebnis") labels, and both decimal and ``0x``-hex value formats — schtasks
    localises the label and may render the code either way depending on the
    Windows UI language.
    """
    for raw in (query_output or "").splitlines():
        if ":" not in raw:
            continue
        label, _, value = raw.partition(":")
        label = label.strip().lower()
        if not ("last result" in label or "letztes ergebnis" in label):
            continue
        token = value.strip().split()[0] if value.strip() else ""
        if not token:
            return None
        try:
            if token.lower().startswith("0x"):
                return int(token, 16)
            return int(token)
        except ValueError:
            return None
    return None


def last_run_result(task: str) -> Optional[int]:
    """Query a task's last-run exit code via ``schtasks /query /v /fo LIST``.

    No elevation. Returns the parsed integer code, or ``None`` if schtasks is
    unavailable / the query failed / the code could not be parsed. Best-effort
    diagnostics helper — callers must tolerate ``None``.
    """
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", task, "/v", "/fo", "LIST"],
            creationflags=_NO_WINDOW,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
            errors="replace", timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return parse_last_result(result.stdout or "")


def describe_last_result(code: Optional[int]) -> str:
    """Human-readable hint for a task's last-run result code.

    Used to surface why a fired task produced no output. Keeps the mapping in
    one place so the GUI status line and the connect-log diagnostic agree.
    """
    if code is None:
        return "could not read the task's last-run result"
    if code == 0:
        return "task reported success (exit 0)"
    if code == TASK_STILL_RUNNING:
        return "task is still running"
    return f"task failed with code 0x{code & 0xFFFFFFFF:08X} ({code})"
