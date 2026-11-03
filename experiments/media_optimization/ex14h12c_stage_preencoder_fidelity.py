#!/usr/bin/env python3
"""EX-14H-12C: audit frame identity before H.264 in a genuine Stage export.

Runs A-B-B-A, isolated project/cache per run. Hooks cv2.remap only inside this
dedicated lab process; hashes its incoming decoded BGR and outgoing projected BGR
frames. No global engine edits; no original or persistent media modifications.
The instrumented timings MUST NOT be treated as performance benchmarks.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

HARNESSED = Path(__file__).with_name("ex14h11_stage_real_hevc_export_abba.py")
if not HARNESSED.exists():
    raise SystemExit("STOP: EX14H11 sibling harness missing")
spec = importlib.util.spec_from_file_location("ex14h11_stage_harness", HARNESSED)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


@contextmanager
def capture_preencoder_frames():
    import core.spherical_motion as sm
    original = sm.cv2.remap
    decoded_input = []
    preencoder_output = []
    dimensions = []

    def audited_remap(*args, **kwargs):
        source = args[0] if args else kwargs.get("src")
        if source is None:
            raise RuntimeError("EX14H12C: no input frame to remap")
        source_view = memoryview(source)
        if not source_view.c_contiguous:
            raise RuntimeError("EX14H12C: input frame not contiguous")
        source_hash = hashlib.sha256(source_view.cast("B")).hexdigest()

        result = original(*args, **kwargs)
        pixels = result
        if pixels is None:
            pixels = kwargs.get("dst")
            if pixels is None and len(args) >= 7:
                pixels = args[6]
        if pixels is None:
            raise RuntimeError("EX14H12C: no remapped output")
        output_view = memoryview(pixels)
        if not output_view.c_contiguous:
            raise RuntimeError("EX14H12C: output frame not contiguous")
        output_hash = hashlib.sha256(output_view.cast("B")).hexdigest()

        decoded_input.append(source_hash)
        preencoder_output.append(output_hash)
        dimensions.append([list(source.shape), list(pixels.shape)])
        return result

    sm.cv2.remap = audited_remap
    try:
        yield {
            "decoded_input": decoded_input,
            "preencoder_output": preencoder_output,
            "dimensions": dimensions,
        }
    finally:
        sm.cv2.remap = original


def main():
    if h.capture(["git", "-C", str(h.ROOT), "rev-parse", "--short", "HEAD"]) != "0f9ec03":
        raise RuntimeError("STOP: unexpected engine commit (must be 0f9ec03)")
    if h.capture(["git", "-C", str(h.ROOT), "status", "--porcelain"]):
        raise RuntimeError("STOP: engine worktree modified")
    if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
        raise RuntimeError("STOP: less than 10 GiB disk free")

    selected = h.source()
    stat_before = (selected.stat().st_size, selected.stat().st_mtime_ns)
    sys.path.insert(0, str(h.ROOT))
    runs = []
    print("EX14H_12C_PREENCODER_ABBA_START", flush=True)
    with tempfile.TemporaryDirectory(prefix="jupiter_ex14h12c_", dir="/home/fer") as tmp:
        for index, mode in enumerate(("A", "B", "B", "A"), 1):
            with capture_preencoder_frames() as frames:
                output = h.run_one(Path(tmp), selected, mode, index)

            decoded = frames["decoded_input"]
            projected = frames["preencoder_output"]
            dims = frames["dimensions"]
            if len(decoded) != 60 or len(projected) != 60:
                raise RuntimeError(f"STOP: expected 60 remaps, got {len(projected)}")
            if any(d != [[1920, 3840, 3], [1080, 1920, 3]] for d in dims):
                raise RuntimeError(f"STOP: unexpected frame dimensions {dims[0]}")
            if stat_before != (selected.stat().st_size, selected.stat().st_mtime_ns):
                raise RuntimeError("STOP: original video changed")
            if shutil.disk_usage("/home/fer").free < 10 * 1024**3:
                raise RuntimeError("STOP: disk free below threshold")

            runs.append({"mode": mode, "index": index,
                         "decoded_hashes": list(decoded),
                         "preencoder_hashes": list(projected),
                         "mp4_decoded_sha": output["rgb_sha256"],
                         "audio_pcm_sha": output["audio_pcm_sha256"]})
            print("EX14H_12C_RUN " + json.dumps({
                "run": index, "mode": mode,
                "decoded_frames": len(decoded), "preencoder_frames": len(projected),
                "decoded_stream_sha": hashlib.sha256("".join(decoded).encode()).hexdigest(),
                "preencoder_stream_sha": hashlib.sha256("".join(projected).encode()).hexdigest(),
                "postencoder_rgb_sha": output["rgb_sha256"],
                "audio_pcm_sha": output["audio_pcm_sha256"]
            }), flush=True)

    for left, right, label in ((0, 3, "A1_A2"), (1, 2, "B1_B2"),
                               (0, 1, "A1_B1"), (3, 2, "A2_B2")):
        pair = {
            "pair": label,
            "decoded_input_exact_frames": sum(x == y for x, y in zip(
                runs[left]["decoded_hashes"], runs[right]["decoded_hashes"])),
            "preencoder_exact_frames": sum(x == y for x, y in zip(
                runs[left]["preencoder_hashes"], runs[right]["preencoder_hashes"])),
            "mp4_decoded_exact": runs[left]["mp4_decoded_sha"] == runs[right]["mp4_decoded_sha"],
        }
        print("EX14H_12C_PAIR " + json.dumps(pair), flush=True)

    all_inputs_exact = len({tuple(r["decoded_hashes"]) for r in runs}) == 1
    all_projected_exact = len({tuple(r["preencoder_hashes"]) for r in runs}) == 1
    all_audio_exact = len({r["audio_pcm_sha"] for r in runs}) == 1
    print("EX14H_12C_RESULT " + json.dumps({
        "decoded_input_exact_all": all_inputs_exact,
        "preencoder_frames_exact_all": all_projected_exact,
        "audio_exact_all": all_audio_exact,
        "interpretation": (
            "Preencoder pixels exact; variation downstream of remap"
            if all_projected_exact and all_inputs_exact else
            "Frames differ before encode; investigate decode/maps/remap"
        ),
        "warning": "Timing includes costly hashing and is NOT a performance metric",
        "media_cleanup": "completed",
    }), flush=True)
    if not all_audio_exact:
        raise RuntimeError("STOP: unexpected audio difference")
    print("EX14H_12C_COMPLETED", flush=True)


if __name__ == "__main__":
    main()
