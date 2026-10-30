#!/usr/bin/env python3
"""FOCUS A/C: read-only preflight of proxy -> original media identity.

Reads a saved Zucker project and edit plan. Never mutates either or invokes
FFmpeg. Reports every path reference, exact mapping, missing files and
ambiguous names, without printing private source paths.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

PATH_KEYS = {"path","source_path","clip_path","normalized_path","proxy_path","paired_path"}

def paths(node, root="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            where=f"{root}.{key}"
            if key in PATH_KEYS and isinstance(value,str) and value:
                yield where,value
            elif isinstance(value,(dict,list)):
                yield from paths(value,where)
    elif isinstance(node,list):
        for i,v in enumerate(node):
            yield from paths(v,f"{root}[{i}]")

def signature(path, hash_bytes=False):
    p=Path(path)
    if not p.is_file():
        return {"exists":False}
    s=p.stat()
    info={"exists":True,"size":s.st_size,"mtime_ns":s.st_mtime_ns}
    if hash_bytes:
        h=hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk)
        info["sha256"]=h.hexdigest()
    return info

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project",type=Path,required=True)
    ap.add_argument("--plan",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    project=json.loads(a.project.read_text())
    plan=json.loads(a.plan.read_text())
    videos=project.get("inputs",{}).get("videos",[])
    if not isinstance(videos,list) or not videos:
        ap.error("Project has no input videos")
    segs=plan.get("segments",[])
    if not isinstance(segs,list) or not segs:
        ap.error("Plan has no segments")

    cameras=[]
    mapping={}
    names=[]
    for i,record in enumerate(videos):
        original=record.get("path")
        normalized=record.get("normalized") or {}
        proxy=normalized.get("path")
        if not original:
            ap.error(f"Camera {i+1} has no original path")
        original= str(original)
        # Avoid accidentally treating a proxy as independent original if no
        # transcoding occurred; this is a read-only audit, not a replacement.
        same=not proxy or str(proxy)==original
        if proxy and not same:
            prev=mapping.setdefault(str(proxy),original)
            if prev != original:
                ap.error("Ambiguous proxy path mapped to multiple originals")
        names.append(Path(original).name.lower())
        cameras.append({
            "camera":i+1,
            "original_basename":Path(original).name,
            "original":signature(original),
            "proxy":signature(proxy) if proxy else None,
            "proxy_separate":not same,
            "cache_key_present":bool(record.get("cache_key")),
            "record_has_clip_id":bool(record.get("clip_id")),
            "normalized_kind":normalized.get("kind"),
        })

    refs=list(paths(plan))
    segments=[]
    missing_references=[]
    for i,segment in enumerate(segs):
        ref=segment.get("source_path") or segment.get("clip_path")
        matched=[j+1 for j,rec in enumerate(videos) if ref in {
            rec.get("path"),(rec.get("normalized") or {}).get("path")
        }]
        if len(matched)!=1:
            missing_references.append({"segment":i+1,"matching_cameras":matched,
                                       "ref_basename":Path(str(ref or "")).name})
        segments.append({
            "segment":i+1,"matching_cameras":matched,
            "has_clip_id":bool(segment.get("clip_id")),
            "has_camera_id":bool(segment.get("camera_id")),
            "has_spherical_shot":bool(segment.get("spherical_shot")),
            "source_vs_clip_same":segment.get("source_path")==segment.get("clip_path"),
            "duration_sec":segment.get("duration_sec"),
        })
    counts=Counter(Path(v).name.lower() for _,v in refs)
    report={
        "status":"INSPECTED_NO_REWRITE",
        "scope":"read-only proxy-original identity preflight, no render",
        "cameras":cameras,
        "segments":segments,
        "plan_path_reference_counts":dict(Counter(k.split(".")[-1] for k,_ in refs)),
        "plan_proxy_references":sum(v in mapping for _,v in refs),
        "duplicate_original_basenames":sorted(k for k,n in Counter(names).items() if n>1),
        "unmatched_or_ambiguous_segments":missing_references,
        "has_distinct_proxy_mapping":bool(mapping),
        "mapping_entries":len(mapping),
        "notes":[
            "No project/plan changes are made. Paths are NOT replaced.",
            "This check is not an identity or visual equivalence certification.",
            "For proxy-original swap the engine must retain clip IDs, timing, camera/projection identity and cache attestation.",
            "A current all-original Stage fixture may show mapping_entries=0; that is not a failure.",
            "Never transfer a proxy cache identity to a different original without correct invalidation.",
        ],
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    print(f"REPORT={a.output}")

if __name__=="__main__":
    main()
