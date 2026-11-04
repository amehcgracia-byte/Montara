"""GitHub Actions Windows smoke test of the frozen Companion EXE.

Build is performed separately by PyInstaller. This smoke test does not use
installed Python to *run* Companion, only to orchestrate and assert its API.
No personal media is processed; no ports are exposed beyond 127.0.0.1.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def request(base, path, payload=None, timeout=4):
    headers = {"Origin": "http://localhost:3000"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as result:
        data = result.read()
        return result.status, json.loads(data) if "json" in result.headers.get("Content-Type", "") else data


def main():
    if sys.platform != "win32":
        raise RuntimeError("Windows runner required")
    exe = Path(sys.argv[1]).resolve()
    assert exe.is_file(), exe

    with tempfile.TemporaryDirectory(prefix="montara-windows-packaged-") as tmp:
        root = Path(tmp)
        source = root / "synthetic.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
            "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", str(source),
        ], check=True, timeout=45)
        size = source.stat().st_size
        with source.open("rb") as f:
            first = f.read(65536)
            f.seek(max(0, size - 65536))
            last = f.read(65536)
        fingerprint = hashlib.sha256(first + last).hexdigest()

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env.update({
            "MONTARA_COMPANION_HOME": str(root / "state"),
            "MONTARA_COMPANION_PORT": str(port),
            "MONTARA_COMPANION_ROOTS": str(root),
        })
        # Prove the packaged EXE is not silently using the runner's FFmpeg.
        # Keep the Windows system directory for OS helpers and DLL resolution.
        env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        assert (exe.parent / "bin" / "ffmpeg.exe").is_file()
        assert (exe.parent / "bin" / "ffprobe.exe").is_file()
        print("PACKAGED_FFMPEG_PATH_ISOLATED", flush=True)
        base = f"http://127.0.0.1:{port}"
        log = root / "companion.log"
        with log.open("wb") as out:
            proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                                    stdout=out, stderr=subprocess.STDOUT)
        try:
            health = None
            for _ in range(80):
                if proc.poll() is not None:
                    raise RuntimeError(f"EXE quit before /health (exit {proc.returncode})")
                try:
                    code, health = request(base, "/health", timeout=2)
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.25)
            assert health and code == 200, "health unavailable"
            assert health["app"] == "montara-companion" and health["ffmpeg"]
            print("PACKAGED_HEALTH_PASS", flush=True)
            code, found = request(base, "/locate", {
                "name": source.name, "size": size, "fingerprint": fingerprint,
            })
            assert code == 200, found
            print("PACKAGED_LOCATE_PASS", flush=True)
            code, job = request(base, "/proxies", {"id": found["id"]})
            assert code == 202, job
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                _, state = request(base, "/proxies/" + job["id"])
                if state["status"] in ("ready", "failed", "skipped"):
                    break
                time.sleep(0.2)
            else:
                raise TimeoutError("packaged proxy did not finish")
            assert state["status"] == "ready", state
            code, data = request(base, "/proxies/" + job["id"] + "/file")
            assert code == 200 and len(data) > 1000
            output = root / "proxy.mp4"
            output.write_bytes(data)
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,avg_frame_rate,color_space,color_transfer,color_primaries",
                "-of", "json", str(output),
            ], capture_output=True, text=True, check=True, timeout=15)
            video = json.loads(probe.stdout)["streams"][0]
            assert video["codec_name"] == "h264" and video["width"] == 640 and video["height"] == 360, video
            assert video["avg_frame_rate"] == "30/1", video
            assert all(video.get(field) == "bt709" for field in
                       ("color_space", "color_transfer", "color_primaries")), video
            print(f"PACKAGED_PROXY_PASS: {len(data)} bytes; {state.get('seconds')} s", flush=True)
            print("WINDOWS_PACKAGED_SMOKE_PASS", flush=True)
        finally:
            # Use the process tree only for this freshly spawned lab EXE.
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15, check=False)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("WARNING: packaged EXE did not stop within 10s", flush=True)
            print("---- COMPANION LOG (tail) ----", flush=True)
            if log.exists():
                print(log.read_text(encoding="utf-8", errors="replace")[-2400:].encode("ascii", "backslashreplace").decode("ascii"), flush=True)


if __name__ == "__main__":
    main()
