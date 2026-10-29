"""SATURNO A/B: call unmodified Zucker _render_plan with full source and QA fragment.
A deliberately narrow native renderer integration gate, NOT a complete Stage E2E.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,time,sys,tempfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/"engine"))
from core.project import create_project,file_record
from core.stages.export import _render_plan

def command(*args,timeout=600):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError(f"command {args[0]} failed: {p.stderr[-1200:]}")
    return p.stdout

def video_pixels(path):
    # RGB24 or YUV? same pixel format canonicalized by ffmpeg to eliminate container metadata.
    p=subprocess.run(["ffmpeg","-nostdin","-loglevel","error","-i",str(path),"-map","0:v:0",
        "-an","-pix_fmt","yuv420p","-f","rawvideo","-"],capture_output=True,timeout=300)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors="replace")[-700:])
    return hashlib.sha256(p.stdout).hexdigest(),len(p.stdout)

def decoded_frame_digests(path):
    probe_result=probe(path)
    v=next(s for s in probe_result["streams"] if s["codec_type"]=="video")
    width,height=int(v["width"]),int(v["height"])
    frame_size=width*height*3//2
    p=subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(path),"-map","0:v:0",
       "-pix_fmt","yuv420p","-f","rawvideo","-"],capture_output=True,timeout=300,check=True)
    if len(p.stdout)%frame_size:raise ValueError("unaligned raw frame bytes")
    return [hashlib.sha256(p.stdout[i:i+frame_size]).hexdigest()
        for i in range(0,len(p.stdout),frame_size)]

def sequence_diagnostics(a,b):
    left=decoded_frame_digests(a);right=decoded_frame_digests(b)
    exact=sum(x==y for x,y in zip(left,right))
    best={"shift":0,"matched":exact}
    for shift in range(-4,5):
        matched=sum(left[i]==right[i+shift] for i in range(max(0,-shift),min(len(left),len(right)-shift)))
        if matched>best["matched"]:best={"shift":shift,"matched":matched}
    return {"A_frames":len(left),"B_frames":len(right),
            "same_index_exact_frames":exact,"best_small_shift":best,
            "A_first_8":left[:8],"B_first_8":right[:8]}

def probe(path):
    return json.loads(command("ffprobe","-v","error","-show_streams","-show_format","-of","json",path))

def measure_render(root,source,master,clip_start,label):
    folder=root/label;folder.mkdir()
    project=create_project(label,str(folder/"QA.zuckervid"))
    project.data.setdefault("settings",{}).setdefault("export",{})["verify_motion"]=False
    project.data.setdefault("settings",{}).setdefault("wizard",{})["platform"]="reel_horizontal"
    record=file_record(str(source.resolve()))
    meta=probe(source)
    stream=next(s for s in meta["streams"] if s["codec_type"]=="video")
    record["probe"]={"width":stream["width"],"height":stream["height"],
        "fps":float(eval_fraction(stream.get("avg_frame_rate","30/1"))),
        "projection":"flat"}
    project.data.setdefault("inputs",{})["videos"]=[record]
    project.data["inputs"]["master"]={"path":str(master.resolve())}
    segment={"source_path":str(source.resolve()),"clip_path":str(source.resolve()),
             "clip_start_sec":clip_start,"master_start_sec":0.0,"duration_sec":2.0}
    output=folder/"export.mp4"
    started=time.perf_counter()
    _render_plan(project,[segment],str(master.resolve()),output,"reel_horizontal",2000000,[],lambda *_:None,master_window_start=0)
    seconds=time.perf_counter()-started
    return {"file":str(output),"elapsed_sec":seconds,"bytes":output.stat().st_size,
        "sha256":hashlib.sha256(output.read_bytes()).hexdigest(),"pixels":video_pixels(output),
        "duration_s":float(probe(output)["format"]["duration"])}

def eval_fraction(s):
    a,b=s.split("/")
    return int(a)/int(b) if int(b) else 30

def main():
    source=REPO/"tests/fixtures/much-to-me/cam-fixed.mp4"
    master=REPO/"tests/fixtures/much-to-me/master.mp3"
    out=Path(os.environ.get("SATURNO_AB_OUT","/tmp/saturno-native-ab"))
    out.mkdir(parents=True,exist_ok=True)
    report={"scope":"unmodified Zucker _render_plan, 2-second single-camera reel_horizontal",
        "full_stage_e2e":False,"status":"NOT_RUN"}
    try:
        for p in [source,master]:
            if not p.is_file():raise FileNotFoundError(str(p))
        a=measure_render(out,source,master,4,"A_full")
        package=out/"B_package";package.mkdir(exist_ok=True)
        fragment=package/"cam-fixed-fragment.mkv"
        command("ffmpeg","-nostdin","-v","error","-y","-ss","4","-i",source,
            "-t","2","-map","0:v:0","-an","-c:v","libx264","-qp","0",
            "-pix_fmt","yuv420p",fragment)
        hidden=source.with_name(source.name+".saturno-hide")
        if hidden.exists():raise ValueError("QA original hidden path already exists")
        source.rename(hidden)
        try:
            b=measure_render(out,fragment,master,0,"B_partial")
            b["original_absent_during_B"]=not source.exists()
        finally:
            hidden.rename(source)
        same_pixels=(a["pixels"]==b["pixels"])
        report.update(frame_comparison=sequence_diagnostics(a["file"],b["file"]),
            status="PASS_NATIVE_AB_PIXELS" if same_pixels else "FAIL_NATIVE_AB_PIXELS",
            A=a,B=b,package_video_bytes=fragment.stat().st_size,full_video_bytes=source.stat().st_size,
            package_fraction=round(fragment.stat().st_size/source.stat().st_size,5),
            audio_limitation="The original master MP3 is shared by A and B; complete source isolation not proved",
            temporal_limitation="Only 2 seconds of one flat camera; not the Stage edit plan or moving 360",
            package_method="H264 lossless reencode of fragment, not copy-only or minimal GOP dependency package")
    except Exception as e:
        report.update(status="BLOCKED_OR_FAILED",error=repr(e))
    (out/"AB_VERDICT.json").write_text(json.dumps(report,indent=2,default=list))
    print(json.dumps(report,indent=2,default=list),flush=True)
    return 0 if report["status"]=="PASS_NATIVE_AB_PIXELS" else 1
if __name__=="__main__":raise SystemExit(main())
