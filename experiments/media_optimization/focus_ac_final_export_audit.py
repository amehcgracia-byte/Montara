#!/usr/bin/env python3
"""Final synthetic FOCUS A/C export audit; ffprobe/JSON only, no render."""
import argparse,json,subprocess,sys
from pathlib import Path
def probe(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration,size:stream=index,codec_type,codec_name,width,height,avg_frame_rate,duration,sample_rate,channels","-of","json",str(path)],capture_output=True,text=True,timeout=40,check=True)
    return json.loads(r.stdout)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--project-dir",type=Path,default=Path("/home/fer/montara-focus-ac-true-edit-01"))
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error("Report exists")
    project=a.project_dir
    plan=json.loads((project/"artifacts/edit_plan.json").read_text())
    manifest=json.loads((project/"artifacts/export_manifest.json").read_text())
    exported=list((project/"exports").rglob("*.mp4"))
    if len(exported)!=1:raise SystemExit(f"Expected exactly one exported MP4; found {len(exported)}")
    media=probe(exported[0])
    seg=manifest.get("performance",{}).get("segments") or []
    videos=[s for s in media.get("streams",[]) if s.get("codec_type")=="video"]
    audios=[s for s in media.get("streams",[]) if s.get("codec_type")=="audio"]
    expected=sum(float(s["duration_sec"]) for s in plan["segments"])
    actual=float(media.get("format",{}).get("duration",0))
    provenance=len(seg)==len(plan["segments"])==6 and all(s.get("rendered_from")=="original" and s.get("cached") is False for s in seg)
    duration_ok=abs(actual-expected)<=1.0
    video_ok=len(videos)==1 and videos[0].get("width")==1920 and videos[0].get("height")==1080
    audio_ok=len(audios)>=1
    checks={"six_uncached_original_segments":provenance,"duration_within_one_second":duration_ok,"1920x1080_video":video_ok,"audio_track_present":audio_ok}
    out={"status":"PASS_METADATA_AND_PROVENANCE" if all(checks.values()) else "REVIEW_REQUIRED",
         "checks":checks,"expected_segment_duration_sec":round(expected,3),
         "output_duration_sec":actual,"streams":media.get("streams",[]),
         "export_name":exported[0].name,"bytes":exported[0].stat().st_size,
         "limitations":["No actual audio listening, no waveform analysis, no decoded-frame parity.",
                        "This result closes only synthetic metadata/provenance gate, not real 4K/360 end to end."]}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(out,ensure_ascii=False,indent=2))
    if out["status"]!="PASS_METADATA_AND_PROVENANCE":sys.exit(1)
if __name__=="__main__":main()
