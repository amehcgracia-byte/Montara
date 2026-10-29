"""SATURNO-22: determine minimal *whole GOP* dependency closure on the SAT-20 clip.

A monotone deletion test is NOT assumed: each candidate is re-muxed and
decoded under the exact windows. Selection only removes complete GOPs,
never re-encodes the payload. Retain first/last as packaging constraints.
"""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.saturno_10.packet_preflight import probe,choose_gops,copy_sparse
OUT=Path(tempfile.gettempdir())/"saturno22-gop"
WINDOWS=((20.,26.),(50.,56.))

def call(args, binary=False):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors="replace")[-1500:])
    return p.stdout if binary else p.stdout.decode()
def window_digest(source,start,end):
    data=call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-threads","2","-ss",str(start),"-i",str(source),
        "-vf","fps=30,format=bgr24","-an","-frames:v",str(round((end-start)*30)),
        "-fps_mode","passthrough","-f","rawvideo","pipe:1"],binary=True)
    return (hashlib.sha256(data).hexdigest(),len(data))
def main():
    OUT.mkdir(exist_ok=True)
    report={"experiment":"SATURNO-22","status":"NOT_RUN","variants":[]}
    try:
        src=OUT/"source.mp4"
        call(["ffmpeg","-v","error","-nostdin","-y","-f","lavfi","-i",
              "testsrc2=size=640x320:rate=30:duration=90","-an","-c:v","libx264",
              "-preset","ultrafast","-crf","24","-g","60","-keyint_min","60",
              "-sc_threshold","0","-bf","0","-x264-params","open-gop=0",
              "-threads:v","1","-pix_fmt","yuv420p",src])
        src_probe=probe(str(src),packets=True)
        groups,selected,_=choose_gops(src_probe["packets"],WINDOWS,1/30)
        assert len(groups)==45 and len(selected)==10,(len(groups),selected)
        reference=[window_digest(src,a,b) for a,b in WINDOWS]
        def check(selection,label):
            if not selection or 0 not in selection or len(groups)-1 not in selection:
                raise AssertionError("Preserve endpoint GOPs")
            target=OUT/f"{label}.mp4"
            copy_sparse(str(src),str(target),src_probe,groups,sorted(selection))
            pr=probe(str(target),packets=True)
            actual=[window_digest(target,a,b) for a,b in WINDOWS]
            exact=actual==reference
            packet_bytes=sum(int(p["size"]) for p in pr["packets"])
            row={"label":label,"selected":sorted(selection),"selected_count":len(selection),
                "container_bytes":target.stat().st_size,"packet_bytes":packet_bytes,
                "all_windows_exact":exact,"window_exact":[a==b for a,b in zip(actual,reference)]}
            report["variants"].append(row)
            print("SATURNO22_VARIANT="+json.dumps({k:v for k,v in row.items() if k!="selected"},separators=(",",":")),flush=True)
            return row
        baseline=check(set(selected),"baseline")
        assert baseline["all_windows_exact"]
        # Deletion-greedy in deterministic order; each candidate is independently
        # compared to both original decode windows, and may fail independently.
        current=set(selected)
        for i in sorted(selected):
            if i in (0,len(groups)-1):continue
            candidate=current-{i}
            verdict=check(candidate,f"try_without_{i}")
            if verdict["all_windows_exact"]:
                current=candidate
        final=check(current,"greedy_final")
        report.update(initial_gops=len(selected),minimum_found_gops=len(current),
            source_bytes=src.stat().st_size,initial_bytes=baseline["container_bytes"],
            final_bytes=final["container_bytes"],source_gops=len(groups),
            same_windows=final["all_windows_exact"],final_selection=sorted(current),
            caveat="Deletion-minimal within tested greedy order, not proven global optimum. Synthetic closed GOP H264, two windows, no Zucker Stage, no audio.")
        report["status"]="GREEDY_GOP_EXACT" if final["all_windows_exact"] else "GOP_OPTIMIZATION_FAILED"
    except Exception as exc:report.update(status="OPERATIONAL_ERROR",error=repr(exc))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(report,indent=2))
        print("SATURNO22_SUMMARY="+json.dumps({k:v for k,v in report.items() if k not in ("variants","final_selection")},separators=(",",":")),flush=True)
    return 0 if report["status"]=="GREEDY_GOP_EXACT" else 1
if __name__=="__main__":raise SystemExit(main())
