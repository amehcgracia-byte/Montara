"""B08: bounded folder inventory for real-world Montara working sets.

Metadata only; no media copied, opened or decoded. Accepts a local user-approved
folder passed via CLI. This is NOT browser folder access or a rendering worker.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".mts", ".m2ts",
         ".wav", ".mp3", ".flac", ".aif", ".aiff", ".m4a", ".ogg"}
VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".mts", ".m2ts"}


def inventory(folder: Path, *, max_files=100000):
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Expected an existing folder")
    start = time.perf_counter()
    counts = {"video": 0, "audio": 0}
    bytes_by_kind = {"video": 0, "audio": 0}
    ignored = 0
    errors = 0
    # Do not traverse symlinked directories or include files outside the root.
    for current, subdirs, files in os.walk(folder, followlinks=False):
        subdirs[:] = [d for d in subdirs if not (Path(current) / d).is_symlink()]
        for name in files:
            path = Path(current) / name
            if path.suffix.lower() not in MEDIA or path.is_symlink():
                ignored += 1
                continue
            if counts["video"] + counts["audio"] >= max_files:
                raise ValueError("Working set exceeds configured file count")
            try:
                size = path.stat().st_size
            except OSError:
                errors += 1
                continue
            kind = "video" if path.suffix.lower() in VIDEO else "audio"
            counts[kind] += 1
            bytes_by_kind[kind] += size
    return {
        "benchmark": "B08-folder-inventory-v1",
        "counts": counts,
        "source_bytes": bytes_by_kind,
        "total_source_bytes": sum(bytes_by_kind.values()),
        "ignored_entries": ignored,
        "stat_errors": errors,
        "elapsed_seconds": round(time.perf_counter() - start, 6),
        "copies_created": 0,
        "note": "Metadata-only scan; duration/FPS/proxy/render costs are not measured.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inventory(args.folder)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
