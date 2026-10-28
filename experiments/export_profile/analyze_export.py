"""Compare ZuckerVideos export performance payloads without changing the engine.
Usage: python experiments/export_profile/analyze_export.py cold_manifest.json warm_manifest.json
"""
import argparse
import json
from pathlib import Path

def read(path):
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    payload=value.get("performance") if isinstance(value,dict) else None
    if not isinstance(payload,dict):
        raise ValueError(f"{path}: missing export performance data")
    return payload

def analyze(cold,warm):
    issues=[]
    for key in ("segment_count","segment_workers"):
        if cold.get(key)!=warm.get(key):
            issues.append(f"{key} differs: {cold.get(key)} vs {warm.get(key)}")
    for tag,item in (("cold",cold),("warm",warm)):
        if not isinstance(item.get("total_wall_sec"),(int,float)) or item["total_wall_sec"]<=0:
            issues.append(f"{tag} has no positive total_wall_sec")
    if issues:
        return {"comparable":False,"issues":issues}
    c_total,w_total=cold["total_wall_sec"],warm["total_wall_sec"]
    phase_rows=[]
    for phase in sorted(set(cold.get("phases") or {})|set(warm.get("phases") or {})):
        c=(cold.get("phases") or {}).get(phase);w=(warm.get("phases") or {}).get(phase)
        if isinstance(c,(int,float)) and isinstance(w,(int,float)) and phase.endswith("_sec"):
            phase_rows.append({"phase":phase,"cold_sec":c,"warm_sec":w,"saving_sec":round(c-w,3)})
    warm_segments=warm.get("segments") or []
    return {"comparable":True,"cold_total_sec":c_total,"warm_total_sec":w_total,
        "total_saved_sec":round(c_total-w_total,3),
        "total_reduction_pct":round((c_total-w_total)/c_total*100,1),
        "cold_render_wall_sec":cold.get("wall_sec"),"warm_render_wall_sec":warm.get("wall_sec"),
        "warm_cache_hits":sum(bool(s.get("cached")) for s in warm_segments),
        "warm_segment_entries":len(warm_segments),
        "phases":sorted(phase_rows,key=lambda x:x["warm_sec"],reverse=True),
        "notes":["Phase times may overlap and do not necessarily sum to total_wall_sec.",
          "Per-segment times can overlap across workers; do not sum as wall time.",
          "Verify same project, edit, quality and build externally."]}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("cold");p.add_argument("warm");a=p.parse_args()
    print(json.dumps(analyze(read(a.cold),read(a.warm)),indent=2,ensure_ascii=False))
