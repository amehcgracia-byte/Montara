#!/usr/bin/env python3
"""OPT-03: inspect previously completed isolated E2E artifacts, read-only.

Does not rerender media, run ffmpeg, or modify the engine. Only inspect bounded
JSON and log metadata; never copy source media or sensitive absolute paths to Git.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    root = args.folder.resolve()
    if not root.is_dir():
        parser.error("E2E folder missing")
    summary = root / "summary.json"
    if not summary.is_file():
        parser.error("summary.json missing; E2E may still be running")
    rows = json.loads(summary.read_text())
    print("=== E2E SUMMARY ===")
    for row in rows:
        print(json.dumps({k: row.get(k) for k in (
            "mode", "passed", "duration", "size",
            "measured_browser_journey_seconds_including_ui_waits_and_download",
            "measured_engine_stage_seconds", "cuts", "camera_usage"
        )}, ensure_ascii=False, indent=2))
    print("=== EXPORT PROFILING FILES ===")
    candidates = []
    # Bounded search only in this already-known test output.
    for base in [root / "data-stage", root / "data-push", root / "data-mix"]:
        if not base.is_dir():
            continue
        for path in base.rglob("*.json"):
            if len(candidates) >= 4000:
                break
            name = path.name.lower()
            if any(x in name for x in ("export", "manifest", "performance", "profile", "plan")):
                candidates.append(path)
    for path in candidates[:40]:
        rel = path.relative_to(root)
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                keys = list(data.keys())
                perf = data.get("performance")
                print(f"{rel}: {path.stat().st_size} bytes; keys={keys[:15]}")
                if isinstance(perf, dict):
                    subset = {k: perf.get(k) for k in (
                        "total_wall_sec", "wall_sec", "segment_count",
                        "segment_workers", "phases", "segments"
                    ) if k in perf}
                    if isinstance(subset.get("segments"), list):
                        segs = subset.pop("segments")
                        subset["segment_entries"] = len(segs)
                        subset["cache_hits"] = sum(bool(s.get("cached")) for s in segs if isinstance(s, dict))
                        subset["slowest_segments"] = sorted([
                            {"elapsed_sec": s.get("elapsed_sec"), "cached": s.get("cached")}
                            for s in segs if isinstance(s, dict) and isinstance(s.get("elapsed_sec"), (int, float))
                        ], key=lambda x: x["elapsed_sec"], reverse=True)[:5]
                    print("  performance=", json.dumps(subset, ensure_ascii=False)[:2200])
        except (OSError, UnicodeError, ValueError):
            pass
    print("=== LOG FILE SUMMARY ===")
    logs = list(root.glob("server-*.log"))
    for path in logs:
        lines = path.read_text(errors="replace").splitlines()
        warnings = Counter()
        for line in lines:
            if re.search(r"\b(error|warning|failed|timeout)\b", line, flags=re.I):
                clean = re.sub(r"/home/[^\s\]\)\"']+", "<local_path>", line)
                warnings[clean[:160]] += 1
        print(f"{path.name}: {len(lines)} lines, {path.stat().st_size} bytes")
        for msg, n in warnings.most_common(8):
            print(f"  {n}x {msg}")
    print("=== NEXT ===")
    print("No render performed. Compare profiling metadata before choosing a CPU optimization.")

if __name__ == "__main__":
    main()
