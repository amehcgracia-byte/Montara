#!/usr/bin/env python3
"""FOCUS A/C: run genuine pinned Zucker EditStage on existing physical proxies.

Uses the prior isolated 2-camera, 20-second synthetic E2E. Reuses physical
360p proxies. Does not mutate E2E, source media, engine or main. No export.
Requires montara-bench and explicit Chema clearance.
"""
import argparse,copy,json,os,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"engine"))
from focus_ac_vm_cpu_guard import sample_cpu,processes

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--project",type=Path,default=Path("/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid/project.json"))
    a.add_argument("--physical-proxies",type=Path,default=Path("/home/fer/montara-focus-ac-physical-01"))
    a.add_argument("--output",type=Path,required=True)
    a.add_argument("--approved-by-chema",action="store_true")
    args=a.parse_args()
    if not args.approved_by_chema:a.error("Require Chema approval")
    if args.output.exists():a.error("Output exists; refusing overwrite")
    cpu=sample_cpu(2);load=os.getloadavg()[0];active=processes()
    if cpu is None or cpu>=65 or load >= (os.cpu_count() or 1)*.75 or active:
        a.error(f"VM busy cpu={cpu} load={load} processes={active}")
    src=args.project.resolve(strict=True)
    project_data=copy.deepcopy(json.loads(src.read_text()))
    src_artifacts=src.parent/"artifacts"
    coverage=copy.deepcopy(json.loads((src_artifacts/"coverage.json").read_text()))
    if coverage.get("platform")!="youtube":a.error("Must be actual YouTube multicam coverage")
    videos=project_data["inputs"]["videos"];sources=coverage["sources"]
    if len(videos)!=2 or len(sources)!=2:a.error("Safety: requires two cameras")
    proxies=[args.physical_proxies/f"camera-{i}-proxy-360p.mp4" for i in (1,2)]
    for p in proxies:
        if not p.is_file():a.error(f"Proxy missing: {p}")
    # Reject ambiguous mapping; arrange by original record order and exact
    # coverage source identity (source_path, not merely basename).
    mapped={}
    for rec,proxy in zip(videos,proxies):
        original=str(Path(rec["path"]).resolve(strict=True))
        normalized=rec.setdefault("normalized",{})
        normalized["path"]=str(proxy.resolve())
        normalized["kind"]="proxy"
        mapped[original]=str(proxy.resolve())
    for source in sources:
        original=str(Path(source.get("source_path") or source["path"]).resolve(strict=True))
        if original not in mapped:a.error(f"Unknown coverage source: {original}")
        source["source_path"]=original
        source["path"]=mapped[original]
        source["filename"]=Path(mapped[original]).name
    if len({s["path"] for s in sources})!=2:a.error("Duplicate proxy mapping")
    from core.project import Project
    from core.stages.edit import EditStage,load_edit_plan
    from core.stages.export import _segment_source_info
    start=time.monotonic()
    out=args.output.resolve()
    out.mkdir(parents=True)
    report={"status":"INCOMPLETE","source_project":src.name,"proxy_files":[p.name for p in proxies],
            "preflight_cpu_percent":round(cpu,2),"preflight_load":round(load,2),
            "is_true_engine_edit_stage":True,
            "limitations":["Synthetic 20-second media, not real cameras.",
                           "EditStage can recompute beats/quality; not an isolated speed benchmark.",
                           "No export or audio/video equivalence proven."]}
    try:
        project=Project(out,project_data)
        project.ensure_dirs()
        project.save()
        (out/"artifacts"/"coverage.json").write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+"\n")
        original_beats=src_artifacts/"beats.json"
        if original_beats.is_file():
            shutil.copy2(original_beats,out/"artifacts"/"beats.json")
        timeline=[]
        def progress(p,msg=None):timeline.append({"percent":p,"detail":str(msg)[:120]})
        EditStage().run(project,progress)
        plan=load_edit_plan(project)
        segs=plan.get("segments") or []
        if not segs:raise RuntimeError("EditStage generated empty plan")
        pairs=[]
        for i,seg in enumerate(segs,1):
            resolved=_segment_source_info(project,seg)
            original=resolved["source_path"]
            expected=mapped.get(original)
            if expected is None:raise RuntimeError(f"Segment {i}: unknown source")
            if resolved["proxy_path"]!=expected:raise RuntimeError(f"Segment {i}: wrong proxy path")
            # Source_path in a plan must be an original, and clip_path should
            # point at proxy for an actual proxy-authored plan.
            if seg.get("clip_path")!=expected or seg.get("source_path")!=original:
                raise RuntimeError(f"Segment {i}: not authored with proxy + original pair")
            pairs.append({"segment":i,"camera_id":seg.get("camera_id"),
                "master_start_sec":seg.get("master_start_sec"),
                "clip_start_sec":seg.get("clip_start_sec"),
                "duration_sec":seg.get("duration_sec"),
                "original_and_proxy_resolve":True})
        report.update({"status":"PASS_TRUE_EDIT_FROM_PROXIES","segments":len(segs),
                       "elapsed_seconds":round(time.monotonic()-start,3),
                       "pairs":pairs,"progress_last":timeline[-4:]})
    except BaseException as ex:
        report.update({"status":"FAIL","error":repr(ex),
                       "elapsed_seconds":round(time.monotonic()-start,3)})
        raise
    finally:
        (out/"focus_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({"status":report["status"],"segments":report.get("segments"),
            "seconds":report.get("elapsed_seconds"),"error":report.get("error"),
            "report":str(out/"focus_report.json")},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
