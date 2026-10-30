#!/usr/bin/env python3
"""FOCUS A/C final synthetic gate: export a genuine proxy-authored edit plan.

Run in isolated project created by focus_ac_true_proxy_edit.py.
No changes to engine, originals or Chema services. Enforces CPU guard and
validates rendered segment source provenance from export_manifest.json.
"""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from focus_ac_vm_cpu_guard import sample_cpu,processes
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-dir",type=Path,default=Path("/home/fer/montara-focus-ac-true-edit-01"))
    ap.add_argument("--approved-by-chema",action="store_true")
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    if not args.approved_by_chema:ap.error("Requires authorization")
    if args.report.exists():ap.error("Report already exists: refuse overwrite")
    cpu=sample_cpu(2);load=os.getloadavg()[0];procs=processes()
    if cpu is None or cpu>=65 or load >=(os.cpu_count() or 1)*.75 or procs:
        ap.error(f"Busy shared VM: CPU={cpu}, load={load}, procs={procs}")
    from core.project import Project
    from core.stages.edit import load_edit_plan
    from core.stages.export import ExportStage,_segment_source_info
    folder=args.project_dir.resolve(strict=True)
    data=json.loads((folder/"project.json").read_text())
    project=Project(folder,data)
    plan=load_edit_plan(project)
    segments=plan.get("segments") or []
    if len(segments)!=6:ap.error("This gate is limited to six synthetic segments")
    original_paths={str(Path(v["path"]).resolve(strict=True)) for v in data["inputs"]["videos"]}
    mappings=[]
    for i,seg in enumerate(segments,1):
        resolved=_segment_source_info(project,seg)
        original=str(Path(resolved["source_path"]).resolve(strict=True))
        proxy=str(Path(resolved["proxy_path"]).resolve(strict=True))
        if original not in original_paths or original==proxy:ap.error(f"bad source/proxy {i}")
        if seg.get("clip_path")!=proxy or seg.get("source_path")!=original:
            ap.error(f"plan doesn't explicitly refer to original and proxy, seg {i}")
        mappings.append({"segment":i,"original":Path(original).name,"proxy":Path(proxy).name})
    data.setdefault("settings",{}).setdefault("export",{})["force_rerender_segments"]=True
    data["settings"]["export"]["segment_workers"]=1
    # Never modify the canonical saved project; changed settings only in memory.
    # This is an isolated lab project and export writes artifacts/exports/cache only.
    report={"status":"INCOMPLETE","project":str(folder),"preflight_cpu_percent":round(cpu,2),
       "segments":len(segments),"mappings":mappings,
       "warnings":["Synthetic media only, not real 4K inputs",
                   "No A/B video or audio sample metrics computed.",
                   "Engine may use FFmpeg caches for nonsegment artifacts."]}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    try:
        progress=[]
        def cb(p,msg=None):
            if not progress or p>=progress[-1][0]+10:progress.append((p,str(msg)[:100]))
        ExportStage().run(project,cb)
        manifest_path=folder/"artifacts"/"export_manifest.json"
        manifest=json.loads(manifest_path.read_text())
        # Do not assume an undocumented schema: surface provenance for review.
        report["manifest_keys"]=sorted(manifest)
        report["manifest_segment_render_summary"]=manifest.get("performance",{}).get("segments")
        report["final_files"]=[{"name":p.name,"bytes":p.stat().st_size} for p in (folder/"exports").rglob("*.mp4")]
        if not report["final_files"]:raise RuntimeError("No MP4 generated in isolated exports")
        report["status"]="PASS_EXPORT_CREATED_PROVENANCE_REVIEW_PENDING"
        report["progress_last"]=progress[-5:]
    except BaseException as exc:
        report["status"]="FAIL";report["error"]=repr(exc)
        raise
    finally:
        report["elapsed_sec"]=round(time.monotonic()-start,3)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
