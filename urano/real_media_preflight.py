"""U13E2A: read-only preflight of EXISTING real video/audio samples.

No downloads, no uploads, no writes, no filesystem mutation, no Engine launch.
Designed for an explicitly authorized private FER lab only. This inspection
does not imply approval for a public beta or a server-capacity benchmark.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


class PreflightError(ValueError):
    pass


SUPPORTED = {".mov", ".mp4", ".m4v", ".insv", ".wav", ".mp3", ".flac", ".m4a"}


def _check_root(path: Path, role: str) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise PreflightError(f"{role} must be an existing, non-symlink absolute directory")
    return path.resolve(strict=True)


def inspect_file(media_root: Path, relative_file: str) -> dict:
    """Return media metadata only; never read file payload into Python."""
    if not isinstance(relative_file, str) or not relative_file or "\x00" in relative_file:
        raise PreflightError("Invalid media path")
    rel = Path(relative_file)
    if rel.is_absolute() or any(part in {".", ".."} for part in rel.parts):
        raise PreflightError("Only clean paths relative to the media root are accepted")
    path = media_root / rel
    if path.is_symlink() or not path.is_file():
        raise PreflightError("Media source is absent or is a symlink")
    path = path.resolve(strict=True)
    if not path.is_relative_to(media_root):
        raise PreflightError("Media file escapes the approved source root")
    if path.suffix.lower() not in SUPPORTED:
        raise PreflightError("Unsupported sample extension")
    try:
        raw = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=30, check=True
        ).stdout
        payload = json.loads(raw)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError,
            json.JSONDecodeError) as exc:
        raise PreflightError("Unable to inspect media with ffprobe") from exc
    streams = payload.get("streams") or []
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if not video and not audio:
        raise PreflightError("File contains no supported video/audio streams")

    def fps(stream: dict, key: str) -> float | None:
        try:
            value = float(Fraction(str(stream.get(key) or "0")))
            return round(value, 3) if value > 0 else None
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    def descriptor(stream: dict, kind: str) -> dict:
        common = {"codec": stream.get("codec_name", "unknown")}
        if kind == "video":
            return {**common,
                    "width": stream.get("width"), "height": stream.get("height"),
                    "fps_avg": fps(stream, "avg_frame_rate"),
                    "fps_nominal": fps(stream, "r_frame_rate"),
                    "pix_fmt": stream.get("pix_fmt"),
                    "rotation": next(
                        (tag.get("rotation") for tag in stream.get("side_data_list", [])
                         if "rotation" in tag), stream.get("tags", {}).get("rotate"))}
        return {**common, "channels": stream.get("channels"),
                "sample_rate": stream.get("sample_rate")}

    info = payload.get("format") or {}
    try:
        duration = float(info["duration"])
    except (KeyError, ValueError, TypeError):
        duration = None
    return {
        "filename": path.name,
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(duration, 3) if duration is not None else None,
        "videos": [descriptor(s, "video") for s in video],
        "audios": [descriptor(s, "audio") for s in audio],
    }


def evaluate(media_root: Path, work_root: Path, cameras: list[str],
             master: str | None, minimum_free_gb: float = 8) -> dict:
    media_root = _check_root(media_root, "media_root")
    work_root = _check_root(work_root, "work_root")
    if work_root == media_root or work_root.is_relative_to(media_root) or media_root.is_relative_to(work_root):
        raise PreflightError("Source and work directories must be disjoint")
    if not cameras:
        raise PreflightError("Select at least one existing camera")
    if type(minimum_free_gb) not in (int, float) or minimum_free_gb < 0:
        raise PreflightError("Invalid free-space threshold")
    free = shutil.disk_usage(work_root).free
    files = [inspect_file(media_root, value) for value in cameras]
    for camera in files:
        if not camera["videos"]:
            raise PreflightError("Selected camera has no video stream")
    master_info = inspect_file(media_root, master) if master else None
    if master_info and not master_info["audios"]:
        raise PreflightError("Master is missing an audio stream")
    return {
        "pass": free >= minimum_free_gb * 1024 ** 3,
        "purpose": "real_sample_preflight_only",
        "writes": False,
        "source_count": len(files) + (master_info is not None),
        "cameras": files,
        "master": master_info,
        "workspace_free_gib": round(free / 1024 ** 3, 2),
        "minimum_free_gib": minimum_free_gb,
        "warning": None if free >= minimum_free_gb * 1024 ** 3
                   else "Insufficient free space: do not start the export",
        "export_tested": False,
        "companion_tested": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only real-sample preflight; no rendering")
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--camera", action="append", required=True)
    parser.add_argument("--master")
    parser.add_argument("--min-free-gb", type=float, default=8)
    args = parser.parse_args()
    try:
        report = evaluate(args.media_root, args.work_root,
                          args.camera, args.master, args.min_free_gb)
    except PreflightError as exc:
        raise SystemExit(f"NOT READY: {exc}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
