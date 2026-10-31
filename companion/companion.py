#!/usr/bin/env python3
"""Montara companion: runs on the person's computer, next to their original videos.

Montara's page asks it for a small version of a video the person dropped; the original
never leaves the computer. A WAV/AIFF becomes a lossless FLAC (same samples, about half
the bytes); the server turns it back into the identical WAV before mixing. Only files the page already holds can be found: a request
must carry the file's name, size and the SHA-256 of its first and last 64 KiB, which
only someone who has the file can compute. Listens on 127.0.0.1 only. Standard library
and FFmpeg only; no window, no wizard. Stop it with Ctrl+C.

Run: python3 companion.py   (or the 'montara-companion' command the installer adds)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "0.2.0"
PORT = int(os.environ.get("MONTARA_COMPANION_PORT", "47820"))
HOME = Path(os.environ.get("MONTARA_COMPANION_HOME", Path.home() / ".montara-companion"))
CACHE = HOME / "proxies"
EDGE = 65536
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mts", ".mkv", ".avi", ".webm"}
AUDIO_SUFFIXES = {".wav", ".aif", ".aiff"}
DEFAULT_ORIGINS = r"https://[a-z0-9-]+\.trycloudflare\.com|https?://(127\.0\.0\.1|localhost)(:\d+)?|https://[a-z0-9-]+\.vercel\.app"
ORIGINS = re.compile("^(" + os.environ.get("MONTARA_COMPANION_ORIGINS", DEFAULT_ORIGINS) + ")$")
SEARCH_BUDGET_SEC = 25

sources: dict[str, Path] = {}
projects: dict[str, Path] = {}
jobs: dict[str, dict] = {}
lock = threading.Lock()


def log(message: str) -> None:
    print(time.strftime("%H:%M:%S"), message, flush=True)


# ---------- tools ----------
def tool(name: str) -> str | None:
    found = shutil.which(name)
    for extra in ("/opt/homebrew/bin", "/usr/local/bin"):
        candidate = Path(extra) / name
        if not found and candidate.is_file():
            found = str(candidate)
    return found


FFMPEG, FFPROBE = tool("ffmpeg"), tool("ffprobe")


def ffmpeg_has(kind: str, name: str) -> bool:
    if not FFMPEG:
        return False
    out = subprocess.run([FFMPEG, "-hide_banner", f"-{kind}"], capture_output=True, text=True).stdout
    return re.search(rf"\s{re.escape(name)}\s", out) is not None


HW_H264 = ffmpeg_has("encoders", "h264_videotoolbox")
SOFT_H264 = ffmpeg_has("encoders", "libx264")
TONEMAP = ffmpeg_has("filters", "zscale") and ffmpeg_has("filters", "tonemap")


# ---------- finding the original ----------
def fingerprint(path: Path) -> str:
    """Same as Montara's resumable upload: SHA-256 of the first and last 64 KiB."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        head = handle.read(EDGE)
        handle.seek(max(0, size - EDGE))
        tail = handle.read(EDGE)
    return hashlib.sha256(head + tail).hexdigest()


def search_roots() -> list[Path]:
    extra = [Path(p).expanduser() for p in os.environ.get("MONTARA_COMPANION_ROOTS", "").split(os.pathsep) if p]
    home = Path.home()
    roots = extra + [home / d for d in ("Movies", "Desktop", "Downloads", "Documents", "Pictures", "Videos")]
    if Path("/Volumes").is_dir():
        roots += sorted(p for p in Path("/Volumes").iterdir() if p.is_dir())
    roots.append(home)
    return [r for r in roots if r.is_dir()]


def candidates(name: str):
    seen = set()
    if sys.platform == "darwin" and shutil.which("mdfind"):  # Spotlight index: instant on indexed disks
        try:
            out = subprocess.run(["mdfind", "-name", name], capture_output=True, text=True, timeout=15).stdout
            for line in out.splitlines():
                path = Path(line)
                if path.name == name and path not in seen:
                    seen.add(path)
                    yield path
        except (OSError, subprocess.TimeoutExpired):
            pass
    deadline = time.monotonic() + SEARCH_BUDGET_SEC
    for root in search_roots():
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"Library", "node_modules"}]
            if name in files:
                path = Path(folder) / name
                if path not in seen:
                    seen.add(path)
                    yield path
            if time.monotonic() > deadline:
                return


def locate(name: str, size: int, print_: str) -> Path | None:
    for path in candidates(name):
        try:
            if path.is_file() and path.stat().st_size == size and fingerprint(path) == print_:
                return path
        except OSError:
            continue
    return None


# ---------- small version ----------
def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_SUFFIXES


def output_path(source_id: str, pending: bool = False) -> Path:
    ext = ".flac" if is_audio(sources[source_id]) else ".mp4"
    return CACHE / f"{source_id}{'.part' if pending else ''}{ext}"


def audio_plan(info: dict) -> dict:
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not audio:
        return {"skip": "no audio stream"}
    codec = str(audio.get("codec_name") or "")
    bits = str(audio.get("bits_per_raw_sample") or audio.get("bits_per_sample") or "")
    if not codec.startswith("pcm_") or codec.startswith(("pcm_f", "pcm_alaw", "pcm_mulaw")) or bits not in {"8", "16", "24", "32"}:
        return {"skip": f"{codec or 'unknown'} audio: uploaded as it is"}
    duration = float(info.get("format", {}).get("duration") or audio.get("duration") or 0)
    return {"audio": True, "duration": duration, "codec": codec, "bits": bits, "channels": audio.get("channels")}


def audio_command(source: Path, target: Path) -> list[str]:
    # Lossless: FLAC keeps every sample and the BWF time reference (as a tag).
    return [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(source), "-map", "0:a:0", "-c:a", "flac",
            "-compression_level", "5", "-progress", "pipe:1", "-nostats", str(target)]

def probe(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout or "{}")


def rate(text: str | None) -> float:
    try:
        num, den = (text or "0/1").split("/")
        return float(num) / float(den) if float(den) else 0.0
    except ValueError:
        return 0.0


def plan(info: dict) -> dict:
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video:
        return {"skip": "no video stream"}
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    spherical = any("spherical" in str(d.get("side_data_type", "")).lower() for d in video.get("side_data_list", []))
    if spherical or (width >= 3840 and width == 2 * height):
        return {"skip": "360 video: uploaded as it is for now"}
    source_fps = rate(video.get("avg_frame_rate")) or rate(video.get("r_frame_rate")) or 30.0
    fps = 25 if abs(source_fps - 25) < 0.6 or abs(source_fps - 50) < 1 else 24 if abs(source_fps - 24) < 0.6 else 30
    hdr = video.get("color_transfer") in {"arib-std-b67", "smpte2084"}
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    return {"fps": fps, "hdr": hdr, "duration": duration, "codec": video.get("codec_name"), "size": [width, height]}


def proxy_command(source: Path, target: Path, p: dict) -> list[str]:
    # Fit inside 1280x720 (landscape) or 608x1080 (portrait): the engine then uses it as is.
    scale = "scale=w='if(gte(iw,ih),min(1280,iw),-2)':h='if(gte(iw,ih),-2,min(1080,ih))':flags=bilinear"
    chain = [scale, f"fps={p['fps']}"]
    if p["hdr"] and TONEMAP:
        chain += ["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709",
                  "tonemap=tonemap=hable:desat=0", "zscale=t=bt709:m=bt709:r=tv"]
    chain.append("format=yuv420p")
    if HW_H264:
        video = ["-c:v", "h264_videotoolbox", "-b:v", "2500k", "-maxrate", "4M", "-bufsize", "8M"]
    else:
        video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "24"]
    head = [FFMPEG, "-hide_banner", "-nostdin", "-y"]
    if HW_H264:
        head += ["-hwaccel", "videotoolbox"]
    return head + ["-i", str(source), "-map", "0:v:0", "-map", "0:a:0?", "-vf", ",".join(chain),
                   "-fps_mode", "cfr", "-r", str(p["fps"]), "-g", str(p["fps"]), *video,
                   "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                   "-metadata:s:v:0", "rotate=0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                   "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(target)]


def make_proxy(source_id: str) -> None:
    job = jobs[source_id]
    source = sources[source_id]
    target = output_path(source_id)
    if target.is_file() and target.stat().st_size:
        job.update(status="ready", progress=1.0, bytes=target.stat().st_size)
        return
    try:
        p = audio_plan(probe(source)) if is_audio(source) else plan(probe(source))
        if p.get("skip"):
            job.update(status="skipped", reason=p["skip"])
            log(f"skip {source.name}: {p['skip']}")
            return
        pending = output_path(source_id, pending=True)
        if p.get("audio"):
            job.update(info={k: p[k] for k in ("codec", "bits", "channels")})
            command = audio_command(source, pending)
            log(f"lossless FLAC of {source.name} ({p['bits']}-bit, {p['channels']} ch)")
        else:
            job.update(info={k: p[k] for k in ("fps", "hdr", "codec", "size")})
            command = proxy_command(source, pending, p)
            log(f"small version of {source.name} ({p['codec']} {p['size'][0]}x{p['size'][1]}{' HDR' if p['hdr'] else ''}, "
                f"{'hardware' if HW_H264 else 'software'} encoder)")
        started = time.monotonic()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        job["process"] = process
        for line in process.stdout:
            if line.startswith("out_time_us=") and p["duration"]:
                try:
                    job["progress"] = min(0.99, int(line.split("=", 1)[1]) / 1e6 / p["duration"])
                except ValueError:
                    pass
        error = process.stderr.read()
        if process.wait() != 0:
            raise RuntimeError(error.strip().splitlines()[-1] if error.strip() else "FFmpeg failed")
        pending.replace(target)
        elapsed = time.monotonic() - started
        job.update(status="ready", progress=1.0, bytes=target.stat().st_size, seconds=round(elapsed, 1))
        log(f"ready {source.name}: {target.stat().st_size / 1e6:.0f} MB "
            f"({100 * target.stat().st_size / max(1, source.stat().st_size):.0f}% of the original) in {elapsed:.0f} s "
            f"({p['duration'] / max(elapsed, 0.1):.1f}x real time)")
    except Exception as error:  # reported to the page, which then uploads the original
        job.update(status="failed", error=str(error)[:300])
        log(f"failed {source.name}: {error}")
    finally:
        job.pop("process", None)


# ---------- project folder on this computer ----------
def choose_folder(prompt: str) -> Path | None:
    """Native folder dialog on a Mac; elsewhere MONTARA_COMPANION_PROJECTS or the home folder."""
    if sys.platform == "darwin":
        script = f'POSIX path of (choose folder with prompt "{prompt}")'
        result = subprocess.run(["osascript", "-e", "activate", "-e", script], capture_output=True, text=True, timeout=900)
        chosen = result.stdout.strip()
        return Path(chosen) if result.returncode == 0 and chosen else None
    return Path(os.environ.get("MONTARA_COMPANION_PROJECTS", str(Path.home()))).expanduser()


def safe_name(text: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w .,()+-]", "-", str(text or "")).strip(" .")[:80]
    return cleaned or fallback


def load_projects() -> None:
    try:
        for key, value in json.loads((HOME / "projects.json").read_text()).items():
            projects[key] = Path(value)
    except (OSError, ValueError):
        pass


def save_projects() -> None:
    (HOME / "projects.json").write_text(json.dumps({k: str(v) for k, v in projects.items()}, indent=2))


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    server_version = f"MontaraCompanion/{VERSION}"

    def log_message(self, *args):  # quiet; our own log lines are enough
        pass

    def origin_ok(self) -> str | None:
        origin = self.headers.get("Origin", "")
        return origin if ORIGINS.match(origin) else None

    def cors(self, origin: str | None) -> None:
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def reply(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.cors(self.origin_ok())
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204 if self.origin_ok() else 403)
        self.cors(self.origin_ok())
        self.send_header("Content-Length", "0")
        self.end_headers()

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 65536:
            raise ValueError("request too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if not self.origin_ok() and self.path != "/health":
            return self.reply(403, {"error": "origin not allowed"})
        if self.path == "/health":
            return self.reply(200, {"app": "montara-companion", "version": VERSION, "ffmpeg": bool(FFMPEG and FFPROBE),
                                    "hardware_encoder": HW_H264, "tonemap": TONEMAP, "lossless_audio": True})
        match = re.fullmatch(r"/proxies/([a-f0-9]{24})(/file)?", self.path)
        if not match or match.group(1) not in jobs:
            return self.reply(404, {"error": "unknown"})
        job = jobs[match.group(1)]
        if not match.group(2):
            return self.reply(200, {k: v for k, v in job.items() if k != "process"})
        target = output_path(match.group(1))
        if job.get("status") != "ready" or not target.is_file():
            return self.reply(409, {"error": "not ready"})
        self.send_response(200)
        self.cors(self.origin_ok())
        self.send_header("Content-Type", "audio/flac" if target.suffix == ".flac" else "video/mp4")
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()
        with target.open("rb") as handle:
            shutil.copyfileobj(handle, self.wfile, 1024 * 1024)

    def do_POST(self):
        if not self.origin_ok():
            return self.reply(403, {"error": "origin not allowed"})
        save = re.fullmatch(r"/projects/([a-f0-9]{16})/save\?name=([^&/]+)", self.path)
        if save:
            return self.save_file(save.group(1), save.group(2))
        try:
            body = self.body()
        except ValueError:
            return self.reply(400, {"error": "invalid request"})
        if self.path == "/locate":
            name, size, print_ = body.get("name"), body.get("size"), body.get("fingerprint")
            if (not isinstance(name, str) or "/" in name or "\\" in name or Path(name).suffix.lower() not in VIDEO_SUFFIXES | AUDIO_SUFFIXES
                    or not isinstance(size, int) or not isinstance(print_, str) or not re.fullmatch(r"[a-f0-9]{64}", print_)):
                return self.reply(400, {"error": "invalid file description"})
            source_id = hashlib.sha256(f"{name}|{size}|{print_}".encode()).hexdigest()[:24]
            if source_id not in sources:
                path = locate(name, size, print_)
                if not path:
                    log(f"not found on this computer: {name}")
                    return self.reply(404, {"error": "not found on this computer"})
                sources[source_id] = path
                log(f"found {name}")
            return self.reply(200, {"id": source_id})
        if self.path == "/proxies":
            source_id = body.get("id")
            if source_id not in sources:
                return self.reply(404, {"error": "locate the file first"})
            with lock:
                stale = jobs.get(source_id, {}).get("status") == "ready" and not output_path(source_id).is_file()
                if source_id not in jobs or stale or jobs[source_id].get("status") == "failed":
                    jobs[source_id] = {"status": "working", "progress": 0.0}
                    threading.Thread(target=make_proxy, args=(source_id,), daemon=True).start()
            return self.reply(202, {"id": source_id})
        if self.path == "/projects":
            folder = choose_folder("Where should Montara keep this project?")
            if not folder or not folder.is_dir():
                return self.reply(409, {"error": "no folder chosen"})
            name = safe_name(body.get("name"), "Montara project")
            root = folder if folder.name == "Montara" else folder / "Montara"
            target = root / name
            target.mkdir(parents=True, exist_ok=True)
            project_id = hashlib.sha256(f"{target}|{time.time()}".encode()).hexdigest()[:16]
            manifest = {"app": "montara", "name": body.get("name"), "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "sources": [s for s in body.get("sources") or [] if isinstance(s, dict)][:200]}
            (target / "montara-project.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
            projects[project_id] = target
            save_projects()
            log(f"project folder: {target}")
            return self.reply(200, {"id": project_id, "folder": str(target)})
        return self.reply(404, {"error": "unknown"})

    def save_file(self, project_id: str, raw_name: str):
        from urllib.parse import unquote
        folder = projects.get(project_id)
        length = int(self.headers.get("Content-Length") or 0)
        if not folder or not folder.is_dir() or length <= 0:
            return self.reply(404, {"error": "unknown project"})
        name = safe_name(unquote(raw_name), "montara-video.mp4")
        target, pending = folder / name, folder / (name + ".part")
        with pending.open("wb") as handle:
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(remaining, 1024 * 1024))
                if not chunk:
                    break
                handle.write(chunk)
                remaining -= len(chunk)
        if remaining:
            pending.unlink(missing_ok=True)
            return self.reply(400, {"error": "incomplete upload"})
        pending.replace(target)
        log(f"saved {target}")
        return self.reply(200, {"saved": str(target)})


def main() -> int:
    if not (FFMPEG and FFPROBE):
        print("Montara companion needs FFmpeg. On a Mac: brew install ffmpeg")
        return 1
    CACHE.mkdir(parents=True, exist_ok=True)
    load_projects()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} is busy: the companion is probably already running.")
        return 1
    log(f"Montara companion {VERSION} ready on 127.0.0.1:{PORT} · encoder: "
        f"{'hardware (VideoToolbox)' if HW_H264 else 'software (libx264)' if SOFT_H264 else 'none'} · "
        f"HDR tone mapping: {'yes' if TONEMAP else 'no'}")
    log("Keep this window open while you use Montara. Ctrl+C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
