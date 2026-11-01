#!/usr/bin/env python3
"""Montara companion: runs on the person's computer, next to their original videos.

Montara's page asks it for a small version of a video the person dropped; the original
never leaves the computer. A WAV/AIFF becomes a lossless FLAC (same samples, about half
the bytes); the server turns it back into the identical WAV before mixing. For a full
session it becomes a light Opus preview instead, and at export the page asks here for
only the song ranges of the originals (lossless). Only files the page already holds can be found: a request
must carry the file's name, size and the SHA-256 of its first and last 64 KiB, which
only someone who has the file can compute. Listens on 127.0.0.1 only. Standard library
and FFmpeg only; no window, no wizard. Stop it with Ctrl+C.

Run: python3 companion.py   (or the 'montara-companion' command the installer adds)
"""
from __future__ import annotations

import functools
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

VERSION = "0.5.0"
PORT = int(os.environ.get("MONTARA_COMPANION_PORT", "47820"))
HOME = Path(os.environ.get("MONTARA_COMPANION_HOME", Path.home() / ".montara-companion"))
CACHE = HOME / "proxies"
EDGE = 65536
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mts", ".mkv", ".avi", ".webm"}
AUDIO_SUFFIXES = {".wav", ".aif", ".aiff"}
DEFAULT_ORIGINS = r"https://[a-z0-9-]+\.trycloudflare\.com|https?://(127\.0\.0\.1|localhost)(:\d+)?|https://[a-z0-9-]+\.vercel\.app"
ORIGINS = re.compile("^(" + os.environ.get("MONTARA_COMPANION_ORIGINS", DEFAULT_ORIGINS) + ")$")
SEARCH_BUDGET_SEC = 25

MIXER_HOME = HOME / "mixer"   # optional: install.sh --mixer (same mixer as the server, songs mixed here)
MIX_SLOTS = threading.Semaphore(max(1, int(os.environ.get("MONTARA_COMPANION_MIX_SLOTS", "1"))))

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
OPUS = ffmpeg_has("encoders", "libopus")
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
    # A session's tracks sit together: look first next to the files already found
    # (external disks are often not in Spotlight and too big to walk in time).
    for folder in dict.fromkeys(p.parent for p in list(sources.values())):
        path = folder / name
        if path.is_file():
            seen.add(path)
            yield path
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


def local_mixer() -> dict | None:
    """The optional local mixer: {"mixer": commit} when installed and usable."""
    python = MIXER_HOME / "venv" / "bin" / "python"
    commit = MIXER_HOME / "MIXER_COMMIT"
    if not (python.is_file() and commit.is_file() and (MIXER_HOME / "local_mix.py").is_file()):
        return None
    return {"mixer": commit.read_text().strip()}


def valid_original(original) -> bool:
    return (isinstance(original, dict) and isinstance(original.get("name"), str) and "/" not in original["name"] and "\\" not in original["name"]
            and isinstance(original.get("size"), int) and not isinstance(original.get("size"), bool)
            and isinstance(original.get("fingerprint"), str) and re.fullmatch(r"[a-f0-9]{64}", original["fingerprint"]) is not None)


def find_original(original: dict) -> Path | None:
    source_id = hashlib.sha256(f"{original['name']}|{original['size']}|{original['fingerprint']}".encode()).hexdigest()[:24]
    if source_id not in sources:
        path = locate(original["name"], original["size"], original["fingerprint"])
        if not path:
            return None
        sources[source_id] = path
    return sources[source_id]


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


@functools.lru_cache(maxsize=512)
def lossless_ext(path: Path) -> str:
    """FLAC for integer PCM; WavPack for 32/64-bit float, which FLAC cannot hold (both lossless)."""
    try:
        return ".wv" if audio_plan(probe(path)).get("float") else ".flac"
    except (OSError, ValueError, subprocess.SubprocessError):
        return ".flac"


def output_path(key: str, pending: bool = False) -> Path:
    """key is a source id, or a source id + 'p' for the light preview of an audio track."""
    ext = ".opus" if key.endswith("p") else lossless_ext(sources[key[:24]]) if is_audio(sources[key[:24]]) else ".mp4"
    return CACHE / f"{key}{'.part' if pending else ''}{ext}"


def audio_plan(info: dict) -> dict:
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not audio:
        return {"skip": "no audio stream"}
    codec = str(audio.get("codec_name") or "")
    bits = str(audio.get("bits_per_raw_sample") or audio.get("bits_per_sample") or "")
    floating = codec.startswith("pcm_f")  # 32/64-bit float: fine for a preview, FLAC cannot hold it
    if not codec.startswith("pcm_") or codec.startswith(("pcm_alaw", "pcm_mulaw")) or (not floating and bits not in {"8", "16", "24", "32"}):
        return {"skip": f"{codec or 'unknown'} audio: uploaded as it is"}
    duration = float(info.get("format", {}).get("duration") or audio.get("duration") or 0)
    return {"audio": True, "duration": duration, "codec": codec, "bits": "float" if floating else bits, "channels": audio.get("channels"),
            "rate": audio.get("sample_rate"), "float": floating}


def preview_command(source: Path, target: Path, p: dict) -> list[str]:
    # Light preview for song detection and the browser mixer; the export uses the originals.
    # The tags let the server decode it back at the original rate with the BWF time reference.
    rate = str(p.get("rate") or 48000)
    bitrate = f"{min(256, 96 * int(p.get('channels') or 1))}k"
    return [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(source), "-map", "0:a:0", "-c:a", "libopus", "-b:a", bitrate,
            "-vbr", "on", "-application", "audio", "-metadata", f"montara_sample_rate={rate}", "-metadata", f"montara_bits={p['bits']}",
            "-progress", "pipe:1", "-nostats", "-f", "ogg", str(target)]


def audio_command(source: Path, target: Path) -> list[str]:
    # Lossless: FLAC (or WavPack for float) keeps every sample and the BWF time reference (as a tag).
    codec = ["-c:a", "wavpack"] if target.suffix == ".wv" else ["-c:a", "flac", "-compression_level", "5"]
    return [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(source), "-map", "0:a:0", *codec,
            "-progress", "pipe:1", "-nostats", str(target)]

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


def make_proxy(key: str) -> None:
    job = jobs[key]
    source = sources[key[:24]]
    target = output_path(key)
    if target.is_file() and target.stat().st_size:
        job.update(status="ready", progress=1.0, bytes=target.stat().st_size)
        return
    try:
        p = audio_plan(probe(source)) if is_audio(source) else plan(probe(source))
        if p.get("skip"):
            job.update(status="skipped", reason=p["skip"])
            log(f"skip {source.name}: {p['skip']}")
            return
        pending = output_path(key, pending=True)
        if p.get("audio"):
            job.update(info={k: p[k] for k in ("codec", "bits", "channels")})
            if key.endswith("p"):
                command = preview_command(source, pending, p)
                log(f"light preview of {source.name} (Opus; the export uses the original)")
            else:
                command = audio_command(source, pending)
                log(f"lossless {'WavPack' if pending.suffix == '.wv' else 'FLAC'} of {source.name} ({p['bits']}, {p['channels']} ch)")
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
                                    "hardware_encoder": HW_H264, "tonemap": TONEMAP, "lossless_audio": True,
                                    "audio_preview": OPUS, "segment_formats": ["lossless"] + (["opus"] if OPUS else []),
                                    "local_mix": local_mixer()})
        match = re.fullmatch(r"/proxies/([a-f0-9]{24}p?)(/file)?", self.path)
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
        self.send_header("Content-Type", {".flac": "audio/flac", ".wv": "audio/x-wavpack", ".opus": "audio/ogg"}.get(target.suffix, "video/mp4"))
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
        if self.path == "/mix-song":
            return self.mix_song(body)
        if self.path == "/proxies":
            source_id = body.get("id")
            if source_id not in sources:
                return self.reply(404, {"error": "locate the file first"})
            preview = body.get("preview") is True and is_audio(sources[source_id]) and OPUS
            key = source_id + ("p" if preview else "")
            with lock:
                stale = jobs.get(key, {}).get("status") == "ready" and not output_path(key).is_file()
                if key not in jobs or stale or jobs[key].get("status") == "failed":
                    jobs[key] = {"status": "working", "progress": 0.0}
                    threading.Thread(target=make_proxy, args=(key,), daemon=True).start()
            return self.reply(202, {"id": key, "preview": bool(preview)})
        if self.path == "/segment":
            return self.send_segment(body)
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

    def mix_song(self, body: dict):
        """Mix one song here with the server's mixer and send back the MP3 (the page uploads it)."""
        mixer = local_mixer()
        if not mixer:
            return self.reply(503, {"error": "the local mixer is not installed"})
        plan = body.get("plan")
        if not isinstance(plan, dict) or not isinstance(plan.get("tracks"), list) or not 0 < len(plan["tracks"]) <= 128:
            return self.reply(400, {"error": "invalid song plan"})
        if plan.get("mixer") != mixer["mixer"]:
            return self.reply(409, {"error": "this companion has another mixer version", "mixer": mixer["mixer"]})
        tracks = []
        for track in plan["tracks"]:
            if not isinstance(track, dict) or not valid_original(track.get("original")) or not isinstance(track.get("file"), str) \
                    or "/" in track["file"] or "\\" in track["file"] or not track["file"].lower().endswith(".wav"):
                return self.reply(400, {"error": "invalid track"})
            path = find_original(track["original"])
            if not path:
                return self.reply(404, {"error": f"{track['original']['name']} was not found on this computer"})
            tracks.append({**track, "path": str(path)})
        mix = body.get("mix") if isinstance(body.get("mix"), dict) else {}
        CACHE.mkdir(parents=True, exist_ok=True)
        ident = f"{os.getpid()}-{threading.get_ident()}-{time.monotonic_ns()}"
        plan_file, output = CACHE / f"mix-{ident}.json", CACHE / f"mix-{ident}.mp3"
        plan_file.write_text(json.dumps({**plan, "tracks": tracks, **{k: mix.get(k) for k in ("faders", "mutes", "effects", "eq") if k in mix}}))
        started = time.monotonic()
        try:
            with MIX_SLOTS:   # one song at a time by default: the mixer uses every core it gets
                done = subprocess.run([str(MIXER_HOME / "venv" / "bin" / "python"), str(MIXER_HOME / "local_mix.py"), str(plan_file), str(output)],
                                      cwd=MIXER_HOME, capture_output=True, text=True, timeout=3600,
                                      env={**os.environ, "MONTARA_FFMPEG": FFMPEG or "ffmpeg"})
            if done.returncode != 0 or not output.is_file():
                log(f"local mix failed: {done.stderr.strip()[-400:]}")
                return self.reply(500, {"error": "the local mix failed", "detail": done.stderr.strip()[-400:]})
            log(f"mixed a song here in {time.monotonic() - started:.0f} s ({output.stat().st_size / 1e6:.1f} MB)")
            self.send_response(200)
            self.cors(self.origin_ok())
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(output.stat().st_size))
            self.send_header("X-Mix-Seconds", f"{time.monotonic() - started:.1f}")
            self.send_header("Access-Control-Expose-Headers", "X-Mix-Seconds")
            self.end_headers()
            with output.open("rb") as handle:
                shutil.copyfileobj(handle, self.wfile, 1024 * 1024)
        except subprocess.TimeoutExpired:
            return self.reply(504, {"error": "the local mix took too long"})
        finally:
            plan_file.unlink(missing_ok=True)
            output.unlink(missing_ok=True)

    def send_segment(self, body: dict):
        """Lossless FLAC of one time range of a located original (a song of a full session)."""
        source_id, start, duration = body.get("id"), body.get("start"), body.get("duration")
        if (source_id not in sources or not is_audio(sources[source_id]) or isinstance(start, bool) or isinstance(duration, bool)
                or not isinstance(start, (int, float)) or not isinstance(duration, (int, float)) or start < 0 or not 0 < duration <= 4 * 3600):
            return self.reply(400, {"error": "invalid segment"})
        source = sources[source_id]
        # A real file, not a pipe: FLAC writes its sample count and checksum at the end.
        CACHE.mkdir(parents=True, exist_ok=True)
        plan = audio_plan(probe(source))
        if body.get("format") == "opus" and OPUS:
            # Fast: high-bitrate Opus, several times lighter than lossless; the server decodes it
            # back to WAV at the original rate (tag). Sample-aligned with the other tracks.
            kind = "opus"
            codec = ["-c:a", "libopus", "-b:a", f"{192 if int(plan.get('channels') or 1) == 1 else 256}k", "-vbr", "on",
                     "-application", "audio", "-metadata", f"montara_sample_rate={plan.get('rate') or 48000}", "-f", "ogg"]
        else:
            kind = "wv" if plan.get("float") else "flac"  # FLAC has no float: WavPack, also lossless
            codec = ["-c:a", "wavpack"] if kind == "wv" else ["-c:a", "flac", "-compression_level", "5"]
        floating = kind == "wv"
        target = CACHE / f"segment-{source_id}-{threading.get_ident()}.{kind}"
        command = [FFMPEG, "-hide_banner", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.6f}", "-t", f"{duration:.6f}", "-i", str(source),
                   "-map", "0:a:0", *codec, str(target)]
        started = time.monotonic()
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=900)
            if done.returncode != 0 or not target.is_file():
                log(f"segment failed {source.name}: {done.stderr.strip()[-200:]}")
                return self.reply(500, {"error": "could not read that part of the original"})
            size = target.stat().st_size
            log(f"original {source.name} {start:.1f}+{duration:.1f} s: {size / 1e6:.0f} MB in {time.monotonic() - started:.1f} s")
            self.send_response(200)
            self.cors(self.origin_ok())
            self.send_header("Content-Type", "audio/ogg" if kind == "opus" else "audio/x-wavpack" if floating else "audio/flac")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with target.open("rb") as handle:
                shutil.copyfileobj(handle, self.wfile, 1024 * 1024)
        finally:
            target.unlink(missing_ok=True)

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
