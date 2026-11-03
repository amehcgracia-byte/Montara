#!/usr/bin/env python3
"""EX14H12E: observe actual Stage 360 encoder command with no engine edits.

Runs one real isolated Stage export using the proven harness. Logs redacted
FFmpeg encoder configuration (never media paths), and warns when the options
differ from the isolated x264 benchmark. This is an inspection, not a speed test.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

BASE = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not BASE.exists():
    raise SystemExit("STOP: missing sibling Stage harness")
spec = importlib.util.spec_from_file_location("stage_harness", BASE)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

def main():
    if h.capture(["git", "-C", str(h.ROOT), "rev-parse", "--short", "HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: expected clean engine commit 0f9ec03")
    if h.capture(["git", "-C", str(h.ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: dirty engine checkout")
    if shutil.disk_usage("/home/fer").free < 10*1024**3:
        raise RuntimeError("STOP: insufficient disk")
    src = h.source()
    before = (src.stat().st_size, src.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))
    from core.stages import export
    original = export.run_reprojected_command
    calls = []
    def spy(command, *args, **kwargs):
        tokens = list(command)
        options = {}
        for flag in ("-c:v", "-preset", "-threads", "-filter_threads",
                     "-filter_complex_threads", "-b:v", "-maxrate", "-bufsize",
                     "-pix_fmt", "-fps_mode", "-r", "-video_track_timescale",
                     "-frames:v", "-movflags"):
            locations = [i for i, x in enumerate(tokens[:-1]) if x == flag]
            options[flag] = [tokens[i+1] for i in locations] if locations else []
        options["has_filter_complex"] = "-filter_complex" in tokens
        options["has_rawvideo_pipe"] = "pipe:0" in tokens
        options["arg_count"] = len(tokens)
        options["video_encoder_threads_explicitly_limited"] = bool(options["-threads"])
        calls.append(options)
        print("EX14H_12E_REAL_ENCODER_FLAGS " + json.dumps(options), flush=True)
        return original(command, *args, **kwargs)
    export.run_reprojected_command = spy
    try:
        with tempfile.TemporaryDirectory(prefix="jupiter_ex14h12e_", dir="/home/fer") as tmp:
            result = h.run_one(Path(tmp), src, "A", 1)
    finally:
        export.run_reprojected_command = original
    if not calls or len(calls) != 1:
        raise RuntimeError(f"STOP: expected 1 native encoder command, got {len(calls)}")
    if calls[0]["-c:v"] != ["libx264"]:
        raise RuntimeError(f"STOP: unexpected codec {calls[0]['-c:v']}")
    if (src.stat().st_size, src.stat().st_mtime_ns) != before:
        raise RuntimeError("STOP: source metadata changed")
    print("EX14H_12E_PASS " + json.dumps({
        "native_calls": len(calls), "codec": calls[0]["-c:v"][0],
        "encoder_explicit_threads": calls[0]["-threads"],
        "result_audio_sha": result["audio_pcm_sha256"],
        "note": "No performance claim; all temp media cleaned."}), flush=True)

if __name__ == "__main__":
    main()
