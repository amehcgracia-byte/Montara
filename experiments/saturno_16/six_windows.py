"""SATURNO-16: six real 360 decoder windows, single fps_mode control."""
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.saturno_14.decoder_window import sha,run,decode,compare,EXPECTED_ENGINE
OUT=Path(tempfile.gettempdir())/"saturno16-decoder"
SEGMENTS=(3,6,8,12,16,19)
def main():
    OUT.mkdir(exist_ok=True)
    report={"experiment":"SATURNO-16","status":"NOT_RUN","segments":{},"tokens_measured":None}
    try:
        assert run(["git","-C",str(ROOT/"engine"),"rev-parse","HEAD"]).strip()==EXPECTED_ENGINE
        report["engine_commit"]=EXPECTED_ENGINE
        report["ffmpeg_version"]=run(["ffmpeg","-version"]).splitlines()[0]
        prev=json.loads((ROOT/"experiments/saturno_14/results_40902865517.json").read_text())["report"]
        original=ROOT/"tests/fixtures/much-to-me/cam-360.mp4"
        baseline=json.loads((ROOT/"experiments/saturno_10/packet_results_40886014059.json").read_text())["report"]
        row=next(x for x in baseline["sources"] if x["source"].endswith("cam-360.mp4"))
        assert sha(original)==row["source_sha256"]==prev["source_sha256"]
        packaged=OUT/"cam-360.mp4"
        cmd=[str(packaged) if x==row["target"] else str(original) if x==row["source"] else x for x in row["command"]]
        run(cmd)
        assert sha(packaged)==row["target_sha256"]==prev["package_sha256"]
        planpath=ROOT/"experiments/saturno_10/stage_edit_plan.json"
        assert sha(planpath)==prev["plan_sha256"]
        plan=json.loads(planpath.read_text())
        width,height=prev["source_size"]
        for index in SEGMENTS:
            segment=plan["segments"][index-1]
            # Segment indices are fixed by the SATURNO-12 audited 360 list.
            start=str(float(segment["clip_start_sec"]))
            frames=max(1,round(float(segment["duration_sec"])*30))
            def args(path,passmode):
                c=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-threads","2",
                   "-ss",start,"-i",str(path),"-vf","fps=30,format=bgr24","-an","-frames:v",str(frames)]
                if passmode:c+=["-fps_mode","passthrough"]
                return c+["-f","rawvideo","pipe:1"]
            results={}
            for label,path,flag in [("A_exact",original,False),("B_exact",packaged,False),
                                    ("A_passthrough",original,True),("A_repeat_passthrough",original,True),
                                    ("B_passthrough",packaged,True)]:
                results[label]=decode(args(path,flag),width,height)
            comparisons={k:compare(results[a],results[b]) for k,a,b in [
                ("AB_exact","A_exact","B_exact"),
                ("AA_passthrough","A_passthrough","A_repeat_passthrough"),
                ("AB_passthrough","A_passthrough","B_passthrough")]}
            report["segments"][str(index)]={"start":start,"requested_frames":frames,
                "frame_counts":{k:v["frame_count"] for k,v in results.items()},
                "comparisons":comparisons,
                "frame_hashes":{k:v["frame_hashes"] for k,v in results.items()}}
            print("SATURNO16_SEGMENT="+json.dumps({"index":index,"counts":report["segments"][str(index)]["frame_counts"],
                  "pairs":{k:{"same":v["same_index_exact"],"exact":v["exact"]} for k,v in comparisons.items()}},separators=(",",":")),flush=True)
        ok=all(all(n==s["requested_frames"] for n in s["frame_counts"].values()) and
               s["comparisons"]["AA_passthrough"]["exact"] and s["comparisons"]["AB_passthrough"]["exact"]
               for s in report["segments"].values())
        report["status"]="SIX_WINDOWS_AB_EXACT" if ok else "SIX_WINDOWS_AB_NOT_EXACT"
    except Exception as e:
        report.update(status="OPERATIONAL_ERROR",error=repr(e))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(report,indent=2))
        print("SATURNO16_REPORT_BEGIN",flush=True)
        print(json.dumps(report,separators=(",",":")),flush=True)
        print("SATURNO16_REPORT_END",flush=True)
        print("SATURNO16_SUMMARY="+json.dumps({"status":report["status"],
          "segments":{k:{"requested":v["requested_frames"],"counts":v["frame_counts"],
          "comparisons":{n:{"same":c["same_index_exact"],"exact":c["exact"],"first":c["first_different_index"]}
          for n,c in v["comparisons"].items()}} for k,v in report["segments"].items()},
          "error":report.get("error")},separators=(",",":")),flush=True)
    return 1 if report["status"]=="OPERATIONAL_ERROR" else 0
if __name__=="__main__":raise SystemExit(main())
