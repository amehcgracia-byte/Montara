#!/usr/bin/env python3
"""FOCUS A/C: verify a proposed proxy-to-original handoff, without rewriting.

Input is an already-produced Zucker project JSON and edit-plan JSON plus an
explicit mapping JSON: {"pairs":[{"proxy":"<absolute>","original":"<absolute>"}]}.
The proxy has to be the path in project.inputs.videos[].normalized.path.
Fail closed for missing, ambiguous or unreferenced sources. No video reads,
no hashing of large originals, no FFmpeg, no source modifications.
"""
import argparse
import collections
import json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project",required=True,type=Path)
    ap.add_argument("--plan",required=True,type=Path)
    ap.add_argument("--mapping",required=True,type=Path)
    ap.add_argument("--report",required=True,type=Path)
    args=ap.parse_args()
    data=json.loads(args.project.read_text())
    plan=json.loads(args.plan.read_text())
    pairs=json.loads(args.mapping.read_text())["pairs"]
    videos=data["inputs"]["videos"]
    segments=plan["segments"]
    if not videos or not segments or not pairs:raise SystemExit("Empty videos, segments or mapping")
    mapping={}
    used=set()
    for pair in pairs:
        proxy=Path(pair["proxy"]).resolve(strict=True)
        original=Path(pair["original"]).resolve(strict=True)
        if not proxy.is_file() or not original.is_file() or proxy==original:
            raise SystemExit("Proxy and original must be distinct regular files")
        if str(proxy) in mapping:raise SystemExit("Duplicate proxy mapping")
        mapping[str(proxy)]=str(original)
    # No basename-only lookup: names cannot establish content identity.
    record_map={}
    for rec in videos:
        original=Path(rec["path"]).resolve(strict=True)
        proxy_path=(rec.get("normalized") or {}).get("path")
        if not proxy_path:raise SystemExit("Project video missing normalized.path")
        proxy=Path(proxy_path).resolve(strict=True)
        if str(proxy) not in mapping or mapping[str(proxy)]!=str(original):
            raise SystemExit("Mapping does not match project original/proxy record")
        if str(original) in record_map:raise SystemExit("Duplicate project original path")
        record_map[str(original)]=str(proxy)
    if len(record_map)!=len(mapping):raise SystemExit("Unused or missing mapping pairs")
    segment_checks=[]
    for index,seg in enumerate(segments,1):
        source=seg.get("source_path")
        clip=seg.get("clip_path")
        if not source or not clip:raise SystemExit(f"Segment {index} missing source_path/clip_path")
        original=Path(source).resolve(strict=True)
        proxy=Path(clip).resolve(strict=True)
        if str(original) not in record_map or record_map[str(original)]!=str(proxy):
            raise SystemExit(f"Segment {index} does not reference matching project original/proxy")
        used.add(str(original))
        duration=float(seg.get("duration_sec") or 0)
        start=float(seg.get("clip_start_sec") if seg.get("clip_start_sec") is not None else -1)
        if duration<=0 or start<0:raise SystemExit(f"Invalid timeline segment {index}")
        segment_checks.append({"segment":index,"original_proxy_mapping":True,
                               "timeline_present":True,"camera_id_present":bool(seg.get("camera_id")),
                               "spherical":bool(seg.get("spherical_shot"))})
    report={"status":"PASS_HANDOFF_PREFLIGHT","cameras":len(videos),"segments":len(segments),
            "distinct_originals_used":len(used),"segment_checks":segment_checks,
            "notes":["Metadata, path and continuity gate only, not image/audio identity proof.",
                     "Source content signatures and decoder frames must be verified in an isolated A/B render.",
                     "No plan rewrite and no cache key migration performed.",
                     "This requires an edit plan actually built while using proxies."]}
    if args.report.exists():raise SystemExit("Report exists, refusing overwrite")
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
