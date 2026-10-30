#!/usr/bin/env python3
"""FOCUS A/C: isolated resolver contract against the pinned ZuckerVideos engine.

Builds an in-memory copy of an existing project/plan. A proxy path is deliberately
different from original, while the video timeline/IDs stay intact.
No FFmpeg, filesystem writes (except optional JSON report), or export.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--project",type=Path,required=True)
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    from core.project import Project
    from core.stages.export import _segment_source_info
    raw=json.loads(a.project.read_text())
    plan=json.loads(a.plan.read_text())
    data=copy.deepcopy(raw)
    segments=copy.deepcopy(plan["segments"])
    videos=data["inputs"]["videos"]
    assert videos and segments
    originals={}
    # Virtual proxy paths need not exist to exercise source resolution.
    for idx,rec in enumerate(videos):
        src=str(rec["path"])
        proxy=str(a.output.parent / f"_virtual_focus_proxy_{idx+1}.mp4")
        if Path(proxy).exists():
            raise RuntimeError(f"Refusing to use an existing path: {proxy}")
        rec.setdefault("normalized",{})["path"]=proxy
        rec["normalized"]["kind"]="proxy"
        originals[src]=proxy
    before=json.dumps(segments,sort_keys=True)
    comparisons=[]
    project=Project(a.project.parent,data)
    for idx,seg in enumerate(segments):
        original=str(seg.get("source_path") or seg.get("clip_path") or "")
        if original not in originals:
            raise RuntimeError(f"Segment {idx+1} does not resolve to an original in project inputs")
        proxy=originals[original]
        # Simulate timeline authored while editing proxy.
        seg["clip_path"]=proxy
        seg["source_path"]=original
        result=_segment_source_info(project,seg)
        assert result["source_path"]==original, f"Segment {idx+1}: original resolution failed"
        assert result["proxy_path"]==proxy, f"Segment {idx+1}: proxy resolution failed"
        assert result["source_path"]!=result["proxy_path"]
        for field in ("camera_id","master_start_sec","clip_start_sec","duration_sec","spherical_shot","motion"):
            assert seg.get(field)==plan["segments"][idx].get(field), f"{field} unexpectedly changed"
        comparisons.append({"segment":idx+1,"resolved_original":True,"resolved_proxy":True,
                            "camera_id_preserved":True,"timing_preserved":True})
    assert json.dumps(plan["segments"],sort_keys=True)==before
    assert json.loads(a.project.read_text())==raw
    result={"status":"PASS_RESOLVER_CONTRACT","engine":str(ROOT/"engine"),
            "cameras":len(videos),"segments":len(segments),"checks":comparisons,
            "limitations":["Proxy paths virtual, not generated/decoded.",
                           "No edit-plan creation from proxies and no final render tested.",
                           "Does not establish fidelity for HDR/360 or changed media metadata.",
                           "No engine or user project files modified."]}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
