#!/usr/bin/env python3
"""Timing record of every finished Montara job on this machine, for docs/lab/RUNS.md.

Reads the engine projects in the data folder (no engine import, standard library only),
prints one JSON line per project whose export finished, newest last. Only file names,
never full paths: the records go to a public repository.

    python3 deploy/vm/run_history.py --data ~/montara-data [--root ~/montara]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


def short(text: str | None) -> str | None:
    return (text or "").strip()[:7] or None


def git_rev(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def machine() -> dict:
    info = {"vcpus": os.cpu_count()}
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                info["cpu"] = line.split(":", 1)[1].strip()
                break
        mem = next(l for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal"))
        info["ram_gb"] = round(int(mem.split()[1]) / 1024 / 1024, 1)
    except (OSError, StopIteration, ValueError):
        pass
    return info


def seconds(stage: dict) -> float | None:
    if stage.get("elapsed_seconds") is not None:
        return round(float(stage["elapsed_seconds"]), 1)
    try:
        start = datetime.fromisoformat(str(stage["started_at"]))
        end = datetime.fromisoformat(str(stage["finished_at"]))
        return round((end - start).total_seconds(), 1)
    except (KeyError, TypeError, ValueError):
        return None


def probe_output(path: Path) -> dict:
    out = {"name": path.name, "size_mb": round(path.stat().st_size / 1e6, 1)}
    try:
        data = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                                         capture_output=True, text=True, timeout=30).stdout or "{}")
        video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        out["duration_s"] = round(float(data.get("format", {}).get("duration") or 0), 1)
        if video:
            out["res"] = f"{video.get('width')}x{video.get('height')}"
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return out


def record(folder: Path, base: dict) -> dict | None:
    try:
        project = json.loads((folder / "project.json").read_text())
    except (OSError, ValueError):
        return None
    stages = project.get("stages") or {}
    export = stages.get("export") or {}
    if export.get("status") not in {"done", "completed", "complete"} and not export.get("finished_at"):
        return None
    times = {name: seconds(stage) for name, stage in stages.items() if isinstance(stage, dict)}
    times = {k: v for k, v in times.items() if v is not None}
    inputs = project.get("inputs") or {}
    videos = []
    for item in inputs.get("videos") or []:
        p = item.get("probe") or {}
        name = Path(str(item.get("path", ""))).name
        videos.append({"name": name, "codec": p.get("video_codec"), "res": f"{p.get('width')}x{p.get('height')}",
                       "fps": p.get("fps"), "hdr": p.get("hdr"), "duration_s": p.get("duration"),
                       "size_mb": round((item.get("size") or 0) / 1e6, 1), "projection": p.get("projection"),
                       "small_version": name.endswith(".small.mp4")})
    master = inputs.get("master")
    wizard = (project.get("settings") or {}).get("wizard") or {}
    exports = sorted((folder / "exports").glob("*.mp4"), key=lambda p: p.stat().st_mtime) if (folder / "exports").is_dir() else []
    return {
        **base,
        "date": export.get("finished_at") or project.get("modified_at"),
        "project": project.get("name") or folder.stem,
        "mode": {"youtube": "Stage", "reel": "Push", "show": "Show"}.get(wizard.get("platform"), wizard.get("platform")),
        "stages_s": times,
        "engine_total_s": round(sum(times.values()), 1),
        "videos": videos,
        "master": Path(str(master.get("path") if isinstance(master, dict) else master or "")).name or None,
        "song_range": wizard.get("audio_trim") or None,
        "output": probe_output(exports[-1]) if exports else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path.home() / "montara-data")
    parser.add_argument("--root", type=Path, default=Path.home() / "montara")
    args = parser.parse_args()
    engine = (args.root / "engine-revision.txt").read_text().strip() if (args.root / "engine-revision.txt").is_file() else git_rev(args.root / "engine", "rev-parse", "HEAD")
    base = {"montara": short(git_rev(args.root, "rev-parse", "HEAD")), "engine": short(engine),
            "mixer": short(git_rev(args.root / "mixer", "rev-parse", "HEAD")), "machine": machine()}
    rows = [r for f in sorted((args.data / "Projects").glob("*.zuckervid")) if (r := record(f, base))]
    for row in sorted(rows, key=lambda r: str(r["date"])):
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
