"""Windows-only subprocess tree cancellation smoke (no external dependencies).

Creates an ephemeral Python worker that spawns a child and records its PID.
Calls the product's stop_process_tree and verifies both processes have exited.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from video_jobs import stop_process_tree


def is_alive(pid):
    kernel = ctypes.windll.kernel32
    # PROCESS_QUERY_LIMITED_INFORMATION (0x1000).
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise OSError("GetExitCodeProcess failed")
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel.CloseHandle(handle)


def main():
    assert os.name == "nt", "Windows runner required"
    with tempfile.TemporaryDirectory(prefix="montara-w3m-tree-") as tmp:
        root = Path(tmp)
        worker = (
            "import subprocess,sys,time; "
            "from pathlib import Path; "
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)']); "
            "Path(sys.argv[1]).write_text(str(child.pid)); "
            "time.sleep(300)"
        )
        parent = subprocess.Popen([sys.executable, "-c", worker, str(root / "child.pid")],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        child = None
        try:
            for _ in range(50):
                if (root / "child.pid").is_file():
                    child = int((root / "child.pid").read_text())
                    break
                if parent.poll() is not None:
                    raise RuntimeError("worker exited before spawning child")
                time.sleep(0.1)
            assert child, "child PID missing"
            assert is_alive(parent.pid) and is_alive(child)
            stop_process_tree(parent)
            assert parent.poll() is not None, "parent still running"
            for _ in range(20):
                if not is_alive(child):
                    break
                time.sleep(0.1)
            assert not is_alive(child), "FFmpeg-like child survived parent cancellation"
            print("W3M_PROCESS_TREE_PASS")
        finally:
            if parent.poll() is None:
                subprocess.run(["taskkill", "/PID", str(parent.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False, timeout=15)
            if child and is_alive(child):
                subprocess.run(["taskkill", "/PID", str(child), "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False, timeout=15)


if __name__ == "__main__":
    main()
