#!/usr/bin/env python3
"""FOCUS REAL MINI: genuine Zucker edit on two real 4-second proxies, then
export 4 seconds selected from original 4K iPhone / 1080p Sony.

Reference beat/master is SYNTHETIC and NOT synchronized to real media.
This proves mechanics only, not real sync or editorial quality. Guarded VM.
Requires montara-bench and explicit consent. Creates isolated project.
"""
import argparse,copy,json,os,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"engine"))
from focus_ac_vm_cpu_guard import sample_cpu,processes
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--approved-by-chema",action="store_true")
    a=p.parse_args()
    if not a.approved_by_chema:p.error("Need Chema clearance")
    if a.output.exists():p.error("Output directory exists. Refusing overwrite")
    cpu=sample_cpu(2);load=os.getloadavg()[0];active=processes()
    if cpu is None or cpu>=65 or load >= (os.cpu_count() or 1)*.75 or active:
        p.error(f"VM busy cpu={cpu},load={load},processes={active}")
    e2e=Path("/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid")
    stage=Path("/home/fer/montara-focus-ac-real-01")
    originals=Path("/home/fer/lab-clips/originales")
    records=[
      ("iphone","IMG_0044.MOV","1-iphone-proxy.mp4"),
      ("sony","C0188.MP4","2-sony-proxy.mp4")]
    data=copy.deepcopy(json.loads((e2e/"project.json").read_text()))
    coverage=copy.deepcopy(json.loads((e2e/"artifacts/coverage.json").read_text()))
    if coverage["platform"]!="youtube":p.error("Expected youtube mode")
    new_records=[];new_sources=[]
    for old_rec,old_src,(camera,filename,proxyname) in zip(data["inputs"]["videos"],coverage["sources"],records):
        original=(originals/filename).resolve(strict=True)
        proxy=(stage/proxyname).resolve(strict=True)
        rec=copy.deepcopy(old_rec);source=copy.deepcopy(old_src)
        rec["path"]=str(original)
        rec["camera_role"]="handheld"
        rec["normalized"]={"path":str(proxy),"kind":"proxy"}
        rec["cache_key"]=None
        rec["probe"]={"valid_video":True,"width":3840 if camera=="iphone" else 1920,
            "height":2160 if camera=="iphone" else 1080,
            "duration":986.825 if camera=="iphone" else 89.76,
            "fps":29.97 if camera=="iphone" else 25,
            "rotation":-180 if camera=="iphone" else 0,
            "video_codec":"h264","hdr":False,"projection":None}
        source["clip_id"]=camera+"-real"
        source["path"]=str(proxy)
        source["source_path"]=str(original)
        source["filename"]=filename
        source["duration_sec"]=4.0
        source["offset_sec"]=0.0
        source["camera_role"]="handheld"
        source["projection"]=None
        source["raw_360"]=False
        source["reel_framing"]={}
        source["confidence"]=20.0
        new_records.append(rec);new_sources.append(source)
    data["inputs"]["videos"]=new_records
    data["settings"]["edit"]["camera_roles"]={str(Path(x["path"])):"handheld" for x in new_records}
    data["settings"]["edit"]["camera_types"]={str(Path(x["path"])):"moving" for x in new_records}
    data["settings"]["edit"]["camera_subjects"]={str(Path(x["path"])):"general" for x in new_records}
    data["settings"]["export"]["segment_workers"]=1
    data["settings"]["export"]["force_rerender_segments"]=True
    coverage["sources"]=new_sources
    coverage["window"]={"start_sec":0.0,"duration_sec":4.0,"trim_start_sec":0.0,"trim_end_sec":4.0,"title":"FOCUS-real-mini"}
    coverage["segments"]=[]
    coverage["clip_diagnostics"]=[]
    coverage["excluded_clips"]=[]
    from core.project import Project
    from core.stages.edit import EditStage,load_edit_plan
    from core.stages.export import ExportStage,_segment_source_info
    out=a.output.resolve();out.mkdir(parents=True)
    report={"status":"INCOMPLETE","original_offset_sec":10.0,
      "reference_master":"synthetic E2E master, UNSYNCHRONIZED with real cameras",
      "cameras":[x[0] for x in records],"cpu_preflight":round(cpu,2),
      "limits":["True engine edit on real 4-second proxies but synthetic music/coverage template",
                "Unknown actual camera-to-master sync; not a real concert timeline test",
                "No quantitative A/B frame/audio parity or visual inspection"]}
    start=time.monotonic()
    try:
        project=Project(out,data);project.ensure_dirs();project.save()
        (out/"artifacts/coverage.json").write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+"\n")
        def progress(n,msg=None):pass
        EditStage().run(project,progress)
        plan=load_edit_plan(project);segs=plan.get("segments") or []
        if not segs or len(segs)>5:raise ValueError(f"Unexpected count: {len(segs)}")
        selected=[]
        for i,seg in enumerate(segs,1):
            orig=_segment_source_info(project,seg)["source_path"]
            if seg.get("source_path")!=orig:raise ValueError(f"Source identity mismatch segment {i}")
            local=float(seg["clip_start_sec"])
            duration=float(seg["duration_sec"])
            if local<0 or local+duration>4.05:raise ValueError("Proxy-time out of range")
            selected.append({"camera":Path(orig).name,"local_proxy_start":local,
               "original_start":local+10,"duration":duration})
            # Export uses absolute timestamp in original; do not change camera IDs.
            seg["clip_start_sec"]=local+10
        (out/"artifacts/edit_plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n")
        report["edit_segments"]=selected
        report["editor_finished_sec"]=round(time.monotonic()-start,3)
        ExportStage().run(project,progress)
        manifest=json.loads((out/"artifacts/export_manifest.json").read_text())
        segstats=manifest.get("performance",{}).get("segments") or []
        if len(segstats)!=len(segs) or not all(x.get("rendered_from")=="original" and x.get("cached") is False for x in segstats):
            raise ValueError(f"Export did not prove all original uncached sources: {segstats}")
        outputs=list((out/"exports").rglob("*.mp4"))
        if len(outputs)!=1:raise ValueError(f"Expected one MP4, got {len(outputs)}")
        report["status"]="PASS_REAL_CAMERA_PROXY_EDIT_ORIGINAL_EXPORT_MECHANICS"
        report["export_segments"]=segstats
        report["output_mp4"]=str(outputs[0])
        report["output_bytes"]=outputs[0].stat().st_size
    except BaseException as err:
        report["status"]="FAIL"
        report["error"]=repr(err)
        raise
    finally:
        report["elapsed_sec"]=round(time.monotonic()-start,3)
        (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
