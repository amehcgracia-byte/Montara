"""SATURNO-17: isolated real Zucker reprojection A/A/B for segment 0003.

Reuses successful SAT-12 encoder argv, same plan and SAT-11 package recipe.
No engine edits, no full exports; QA decoder is monkeypatched only in this worker.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.saturno_14.decoder_window import sha,run,EXPECTED_ENGINE
from experiments.saturno_17.qa_decoder_override import cpu_decoder_passthrough_guard

OUT=Path(tempfile.gettempdir())/"saturno17-reprojection"
def main():
    OUT.mkdir(exist_ok=True)
    report={"experiment":"SATURNO-17","status":"NOT_RUN","runs":{}}
    try:
        assert run(["git","-C",str(ROOT/"engine"),"rev-parse","HEAD"]).strip()==EXPECTED_ENGINE
        report["engine_commit"]=EXPECTED_ENGINE
        report["ffmpeg_version"]=run(["ffmpeg","-version"]).splitlines()[0]
        previous=json.loads((ROOT/"experiments/saturno_14/results_40902865517.json").read_text())["report"]
        source=ROOT/"tests/fixtures/much-to-me/cam-360.mp4"
        assert sha(source)==previous["source_sha256"]
        package=OUT/"cam-360.mp4"
        original_command=previous["package_command"]
        cmd=[str(source) if x==original_command[original_command.index("-i")+1] else
             str(package) if x==original_command[-1] else x for x in original_command]
        run(cmd)
        assert sha(package)==previous["package_sha256"]
        planpath=ROOT/"experiments/saturno_10/stage_edit_plan.json"
        assert sha(planpath)==previous["plan_sha256"]
        seg=json.loads(planpath.read_text())["segments"][2]
        assert round(float(seg["duration_sec"])*30)==278
        a=json.loads((ROOT/"experiments/saturno_12/A.json").read_text())
        match=[x for x in a["commands"] if x.get("kind")=="native_360" and
               "error" not in x and str(x["effective_command"][-1]).endswith("segment-0003.mp4")]
        assert len(match)==1, f"Expected one successful native encoder command, got {len(match)}"
        encoder_template=match[0]["effective_command"]
        assert "-threads:v" in encoder_template and encoder_template[encoder_template.index("-threads:v")+1]=="1"
        assert encoder_template.count("pipe:0")==1
        sys.path.insert(0,str(ROOT/"engine"))
        from core.spherical_motion import run_reprojected_command
        import subprocess
        def hashes(path):
            raw=run(["ffmpeg","-nostdin","-v","error","-i",str(path),"-map","0:v:0",
                     "-an","-c:v","rawvideo","-threads:v","1","-pix_fmt","yuv420p",
                     "-fps_mode","passthrough","-f","framehash","-hash","sha256","-"])
            return [x.rsplit(",",1)[-1].strip() for x in raw.splitlines() if x and not x.startswith("#")]
        for label,path in [("A",source),("A_repeat",source),("B",package)]:
            destination=OUT/(label+".mp4")
            command=list(encoder_template)
            command[-1]=str(destination)
            with cpu_decoder_passthrough_guard() as evidence:
                run_reprojected_command(command,str(path),(640,320),
                    float(seg["clip_start_sec"]),278,seg["spherical_shot"],
                    output_size=(1920,1080),fps=30,hardware_decode=False)
            assert len(evidence["interventions"])==1, f"Expected exactly one native decoder, got {evidence}"
            assert destination.exists() and destination.stat().st_size>0
            frames=hashes(destination)
            report["runs"][label]={"file_sha256":sha(destination),"bytes":destination.stat().st_size,
                "frames":len(frames),"hashes":frames,
                "decoder_original":evidence["interventions"][0]["original"],
                "decoder_effective":evidence["interventions"][0]["effective"]}
            print("SATURNO17_RUN="+json.dumps({"label":label,"frames":len(frames),
                "bytes":destination.stat().st_size,"interventions":len(evidence["interventions"])}),flush=True)
        rows=report["runs"]
        report["AA_same"]=sum(x==y for x,y in zip(rows["A"]["hashes"],rows["A_repeat"]["hashes"]))
        report["AB_same"]=sum(x==y for x,y in zip(rows["A"]["hashes"],rows["B"]["hashes"]))
        report["frame_counts"]={k:v["frames"] for k,v in rows.items()}
        if len(set(report["frame_counts"].values())) !=1 or rows["A"]["frames"]!=278:
            report["status"]="FRAME_COUNT_MISMATCH"
        elif rows["A"]["hashes"]!=rows["A_repeat"]["hashes"]:
            report["status"]="UNSTABLE_AA"
        elif rows["A"]["hashes"]==rows["B"]["hashes"]:
            report["status"]="REAL_REPROJECTION_AB_EXACT"
        else:
            report["status"]="REAL_REPROJECTION_AB_DIFFERS"
    except Exception as e:
        report.update(status="OPERATIONAL_ERROR",error=repr(e))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(report,indent=2))
        print("SATURNO17_SUMMARY="+json.dumps({k:v for k,v in report.items() if k!="runs"},separators=(",",":")),flush=True)
    return 1 if report["status"]=="OPERATIONAL_ERROR" else 0
if __name__=="__main__":
    raise SystemExit(main())
