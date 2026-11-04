"""Windows W3N: emulate tray exit during a real active FFmpeg child.

Uses a bounded synthetic FFmpeg lavfi stream in real time, without private video
or network. Parent owns FFmpeg and is killed via the same PID-tree command used
by the tray. Proves the child stops too. No product release or UI interaction.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def alive(pid):
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            raise OSError("GetExitCodeProcess failed")
        return exit_code.value == 259
    finally:
        kernel.CloseHandle(handle)


def kill_tree(pid):
    return subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=15, check=False,
    )


def main():
    assert os.name == "nt", "Windows-only test"
    with tempfile.TemporaryDirectory(prefix="montara-w3n-active-ffmpeg-") as tmp:
        directory = Path(tmp)
        file = directory / "ffmpeg-child.pid"
        # -re throttles a lavfi source to real time; low resolution for low CPU.
        # The worker is structurally like a real Companion process owning a
        # long-running encoder, but does not pretend to exercise Companion UI.
        child_code = (
            "import subprocess,sys,time; from pathlib import Path; "
            "p=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error',"
            "'-nostdin','-re','-f','lavfi','-i','testsrc2=size=160x90:rate=10',"
            "'-t','90','-f','null','NUL'],"
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
            "stderr=subprocess.DEVNULL); "
            "Path(sys.argv[1]).write_text(str(p.pid)); "
            "p.wait()"
        )
        parent = subprocess.Popen(
            [sys.executable, "-c", child_code, str(file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        ffmpeg_pid = None
        try:
            for _ in range(80):
                if file.is_file():
                    ffmpeg_pid = int(file.read_text())
                    if alive(ffmpeg_pid):
                        break
                if parent.poll() is not None:
                    raise RuntimeError(f"parent exited early {parent.returncode}")
                time.sleep(0.1)
            assert ffmpeg_pid and alive(ffmpeg_pid), "FFmpeg never became active"
            assert alive(parent.pid), "parent already exited"
            print("W3N_ACTIVE_FFMPEG_RUNNING", flush=True)
            result = kill_tree(parent.pid)
            assert result.returncode == 0, result.stdout + result.stderr
            parent.wait(timeout=8)
            for _ in range(30):
                if not alive(ffmpeg_pid):
                    break
                time.sleep(0.1)
            assert not alive(ffmpeg_pid), "orphaned FFmpeg remains"
            print("W3N_ACTIVE_FFMPEG_EXIT_PASS", flush=True)
        finally:
            if parent.poll() is None:
                kill_tree(parent.pid)
            if ffmpeg_pid and alive(ffmpeg_pid):
                kill_tree(ffmpeg_pid)


if __name__ == "__main__":
    main()
