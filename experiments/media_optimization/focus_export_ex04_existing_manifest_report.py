#!/usr/bin/env python3
"""FOCUS EXPORT EX-04: report existing export_manifest.performance, read-only.

No rendering, ffprobe, subprocesses, or writes. Prints no filesystem paths.
"""
import json
from pathlib import Path

HOME=Path("/home/fer")
PROJECTS=(
 "montara-focus-iphone-original-03",
 "montara-focus-real-mini-01",
 "montara-focus-ac-true-edit-01",
)
def main():
 for name in PROJECTS:
  root=HOME/name
  manifest=root/"artifacts/export_manifest.json"
  edit=root/"artifacts/edit_plan.json"
  if not manifest.is_file():
   print(json.dumps({"project":name,"status":"manifest_missing"}));continue
  data=json.loads(manifest.read_text())
  p=data.get("performance") or {}
  plan=json.loads(edit.read_text()) if edit.is_file() else {}
  segments=plan.get("segments") or []
  stats=p.get("segments") or []
  print(json.dumps({"project":name,"performance":{
    "total_wall_sec":p.get("total_wall_sec"),"segment_wall_sec":p.get("wall_sec"),
    "workers":p.get("segment_workers"),"segment_count":p.get("segment_count"),
    "phases":p.get("phases")},
    "edit_segments":len(segments),"render_stats":len(stats)},ensure_ascii=False))
  for n,s in enumerate(stats):
   plan_seg=segments[n] if n<len(segments) else {}
   # Match index if available; logs are usually already sorted.
   index=s.get("index")
   if isinstance(index,int) and 1<=index<=len(segments):plan_seg=segments[index-1]
   row={"project":name,"segment":index or n+1,
     "duration_sec":s.get("duration_sec",plan_seg.get("duration_sec")),
     "projection":plan_seg.get("projection"),
     "camera_id":plan_seg.get("camera_id"),
     "cached":s.get("cached"),
     "rendered_from":s.get("rendered_from"),
     "ffmpeg_sec":s.get("ffmpeg_sec"),
     "verify_sec":s.get("verify_sec"),
     "total_sec":s.get("total_sec"),
     "stats_fields":sorted(s.keys())}
   print(json.dumps(row,ensure_ascii=False))
 print("REPORT_COMPLETE_NO_CHANGES")
if __name__=="__main__":main()
