"""W3Q unattended smoke of the *actual* Windows tray launcher.

Runs the PowerShell WinForms event loop with opt-in marker autoexit after
/health, and ensures its owned bundled EXE is stopped on normal tray exit.
This does not validate human visual appearance or user click gestures.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request


def reachable():
    try:
        with urllib.request.urlopen("http://127.0.0.1:47820/health", timeout=1) as res:
            return res.status == 200
    except OSError:
        return False


def main():
    if os.name != "nt":
        raise RuntimeError("Windows runner only")
    folder = Path(sys.argv[1]).resolve()
    launcher = folder / "windows_tray.ps1"
    exe = folder / "MontaraCompanion.exe"
    assert launcher.is_file() and exe.is_file()
    assert not reachable(), "Refusing to test against an existing Companion"
    with tempfile.TemporaryDirectory(prefix="montara-w3q-") as tmp:
        root = Path(tmp)
        marker = root / "tray-success.txt"
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(root / "appdata")
        env["MONTARA_TRAY_SMOKE_MARKER"] = str(marker)
        # Explicitly remove accidental exe override and use real one-folder.
        env.pop("MONTARA_COMPANION_EXE", None)
        proc = subprocess.Popen([
            "powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy",
            "Bypass", "-File", str(launcher),
        ], cwd=str(folder), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                if marker.exists():
                    proc.wait(timeout=12)
                    break
                time.sleep(0.2)
            assert proc.poll() is not None, "Tray did not exit after health"
            assert proc.returncode == 0, f"Tray exited with {proc.returncode}"
            assert marker.exists(), "Tray did not confirm HTTP health"
            assert marker.read_text() == "W3Q_TRAY_HEALTH_PASS"
            for _ in range(30):
                if not reachable():
                    break
                time.sleep(0.2)
            assert not reachable(), "Bundled EXE remained serving after tray exit"
            print("W3Q_TRAY_AUTOMATED_LIFECYCLE_PASS", flush=True)
        finally:
            if proc.poll() is None:
                # Scope forced cancellation to the process started by the test.
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True, check=False, timeout=15)
            try:
                output = proc.communicate(timeout=8)[0]
            except subprocess.TimeoutExpired:
                output = b""
            if output:
                print(output.decode("utf-8", "replace")[-1500:].encode("ascii", "backslashreplace").decode("ascii"))


if __name__ == "__main__":
    main()
