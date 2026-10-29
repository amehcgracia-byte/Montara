"""Audit saved SATURNO-12 evidence offline; never invokes a renderer or network."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

HERE = Path(__file__).resolve().parent
def read(name):
    return json.loads((HERE / name).read_text())

def timeline(evidence):
    raw = zlib.decompress(base64.b64decode(evidence["timeline_zlib_base64"]))
    assert hashlib.sha256(raw).hexdigest() == evidence["timeline_sha256"]
    return json.loads(raw)

def equal(a, b):
    return a == b

def segments(evidence):
    return {Path(c["effective_command"][-1]).name: c for c in evidence["commands"]
            if not c.get("error") and Path(c["effective_command"][-1]).name.startswith("segment-")}

def audit():
    a, ar, b, report = [read(n + ".json") for n in ("A", "A_repeat", "B", "REPORT")]
    for evidence in (a, ar, b):
        assert evidence["frame_count"] == len(evidence["frame_hashes"]) == evidence["expected_frames"] == 3007
        assert evidence["cache_initially_empty"] is True
        assert evidence["native_360_calls"] == 7
    assert a["project_json_sha256"] == ar["project_json_sha256"]
    assert a["plan_json_sha256"] == ar["plan_json_sha256"]
    assert len(b["masked_directories"]) == 3
    assert len(b["original_paths_absent"]) == 4 and all(b["original_paths_absent"].values())
    for label, other in (("AA", ar), ("AB", b)):
        pairs = list(zip(a["frame_hashes"], other["frame_hashes"]))
        result = {
            "frames_A": a["frame_count"], "frames_B": other["frame_count"],
            "expected": a["expected_frames"],
            "video_exact": a["frame_hashes"] == other["frame_hashes"],
            "different_indices": [i for i, (x, y) in enumerate(pairs) if x != y],
            "same_index_exact": sum(x == y for x, y in pairs),
            "audio_exact": a["audio_pcm"] == other["audio_pcm"] and a["audio_pcm"]["bytes"] > 0,
            "timeline_exact": a["timeline_sha256"] == other["timeline_sha256"],
            "file_exact": a["sha256"] == other["sha256"],
        }
        assert result == report[label], label
    ta, tar, tb = map(timeline, (a, ar, b))
    assert ta == tar
    presentation = {}
    for stream in a["streams"]:
        idx = stream["index"]
        pa = [p for p in ta["packets"] if p["stream_index"] == idx]
        pb = [p for p in tb["packets"] if p["stream_index"] == idx]
        presentation[stream["codec_type"]] = {
            "packets_A": len(pa), "packets_B": len(pb),
            "full_packet_list_equal": pa == pb,
            "sorted_pts_duration_equal": sorted((p.get("pts"), p.get("duration")) for p in pa)
                == sorted((p.get("pts"), p.get("duration")) for p in pb),
        }
    sa, sb = segments(a), segments(b)
    rows = []
    assert set(sa) == set(sb) and len(sa) == 19
    for name in sorted(sa):
        x, y = sa[name], sb[name]
        rows.append({
            "output": name, "kind": x["kind"],
            "A_sha256": x["output_sha256"], "B_sha256": y["output_sha256"],
            "same": x["output_sha256"] == y["output_sha256"],
            "encoder_arguments_except_output_equal":
                x["effective_command"][:-1] == y["effective_command"][:-1]
                if x["kind"] == "native_360" else None,
        })
    assert rows == read("intermediate_comparison.json")
    return {
        "audit": "PASS_SAVED_EVIDENCE_CONSISTENCY",
        "scope": "Offline reconstruction from saved job log JSON; no new renders; reported MP4 hashes not recomputed from media.",
        "AA_same_frames": report["AA"]["same_index_exact"],
        "AB_same_frames": report["AB"]["same_index_exact"],
        "presentation": presentation,
        "flat_segments_exact": sum(r["same"] for r in rows if r["kind"] == "ordinary"),
        "native_360_segments_exact": sum(r["same"] for r in rows if r["kind"] == "native_360"),
        "different_native_360_segments": [r["output"] for r in rows if r["kind"] == "native_360" and not r["same"]],
        "native_encoder_arguments_equal_except_output": all(r["encoder_arguments_except_output_equal"] for r in rows if r["kind"] == "native_360"),
        "failed_encoder_attempts_per_run": {e["label"]: sum(bool(c.get("error")) for c in e["commands"]) for e in (a, ar, b)},
    }

if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
