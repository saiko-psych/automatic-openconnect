r"""MANUAL Windows robustness test — DISRUPTS your live VPN connection.

Run ONLY when you don't need the Uni VPN for a few minutes. It drives the REAL
scheduled tasks (connect / disconnect / the crash-recovery path) and proves:

  1. a fresh connect actually establishes (openconnect running AND the uni route
     143.50.0.0/16 is in the route table — NOT just a line in the log, which can
     be stale),
  2. after an abrupt death (crash / logoff: hard-kill, no teardown) the
     conflicting-service MARKER survives and a service is left stopped,
  3. the GUI-startup recovery (_restore_orphaned_services) restarts those
     services and clears the marker,
  4. the next connect self-heals (kill-stale + orphaned-adapter cleanup).

Success is checked via is_vpn_up() + Get-NetRoute, never via the connect-log
text (the bug class that fooled an earlier ad-hoc test).

    .venv\Scripts\python.exe scripts\live_robustness_test.py --yes-disrupt-my-vpn
"""
from __future__ import annotations

import subprocess
import sys
import time

from automatic_openconnect import _windows as w, tasks_windows as tw

UNI_ROUTE = "143.50.0.0/16"          # uni split-include route = proof of a tunnel
CONFLICTING = ["csc_vpnagent", "MullvadVPN"]


def _ps(cmd: str) -> str:
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True).stdout.strip()


def has_uni_route() -> bool:
    return "True" in _ps(f"[bool](Get-NetRoute -DestinationPrefix '{UNI_ROUTE}' "
                         f"-EA SilentlyContinue)")


def connected() -> bool:
    return w.is_vpn_up() and has_uni_route()


def svc(name: str) -> str:
    out = subprocess.run(["sc", "query", name], capture_output=True, text=True).stdout
    return "RUNNING" if "RUNNING" in out else "STOPPED"


def svc_line() -> str:
    return " ".join(f"{n}={svc(n)}" for n in CONFLICTING)


def wait(pred, secs: int, label: str) -> bool:
    for _ in range(max(1, secs // 2)):
        if pred():
            print(f"   [{label}] OK")
            return True
        time.sleep(2)
    print(f"   [{label}] TIMEOUT after {secs}s")
    return False


def main() -> int:
    if "--yes-disrupt-my-vpn" not in sys.argv:
        print(__doc__)
        print("Refusing to run without --yes-disrupt-my-vpn (it cuts your VPN).")
        return 1
    if not tw.is_registered():
        print("Tasks not registered — open the app once (Configuration → Save).")
        return 1

    print("=== STEP 0: clean slate (disconnect) ===")
    tw.run(tw.TASK_DOWN); tw.end(tw.TASK_UP)
    wait(lambda: not w.is_vpn_up(), 30, "disconnected")

    print("=== STEP 1: fresh CONNECT (real auth browser pops) ===")
    tw.run(tw.TASK_UP)
    ok_connect = wait(connected, 200, "connected + uni route present")
    print(f"   marker (services WE stopped) = {w.read_services_marker()}")
    print(f"   services: {svc_line()}")

    print("=== STEP 2: simulate CRASH / LOGOFF (hard kill, NO teardown) ===")
    tw.end(tw.TASK_UP)
    subprocess.run(["taskkill", "/F", "/IM", "openconnect.exe"],
                   capture_output=True)
    time.sleep(4)
    marker_survived = bool(w.read_services_marker())
    print(f"   openconnect up = {w.is_vpn_up()} | marker survived = {marker_survived}")
    print(f"   services: {svc_line()}   (expect at least one STOPPED, marker set)")

    print("=== STEP 3: GUI-startup RECOVERY (_restore_orphaned_services) ===")
    if w.read_services_marker() and not w.is_vpn_up() and tw.is_registered():
        tw.run(tw.TASK_DOWN)             # exactly what the GUI does on startup
    cleared = wait(lambda: not w.read_services_marker(), 20, "marker cleared")
    time.sleep(3)
    print(f"   services: {svc_line()}   (expect BOTH RUNNING again)")

    print("=== STEP 4: RECONNECT — self-heal after the abrupt death ===")
    tw.run(tw.TASK_UP)
    ok_reconnect = wait(connected, 200, "reconnected + uni route present")

    print("=== STEP 5: clean DISCONNECT ===")
    tw.run(tw.TASK_DOWN); tw.end(tw.TASK_UP)
    wait(lambda: not w.is_vpn_up(), 30, "disconnected")
    print(f"   services: {svc_line()}   (expect BOTH RUNNING)")

    print("\n===== RESULT =====")
    print(f" 1) fresh connect establishes ....... {'PASS' if ok_connect else 'FAIL'}")
    print(f" 2) marker survives crash ........... {'PASS' if marker_survived else 'FAIL'}")
    print(f" 3) startup restores services ....... {'PASS' if cleared else 'FAIL'}")
    print(f" 4) reconnect self-heals ............ {'PASS' if ok_reconnect else 'FAIL'}")
    all_ok = ok_connect and marker_survived and cleared and ok_reconnect
    print("=" * 18, "ALL PASS" if all_ok else "SOME FAIL")
    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
