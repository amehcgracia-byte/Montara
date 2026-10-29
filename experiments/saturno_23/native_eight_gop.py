"""SATURNO-23: Zucker-native 360 reprojection using genuine sparse-GOP media.
Two nonadjacent windows, bitwise A/A and A/B MP4 equality, without originals in B.
Synthetic equirectangular-like input; no product engine edits.
"""
import hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.saturno_10.packet_preflight import probe,choose_gops,copy_sparse
from experiments.saturno_17.qa_decoder_override import cpu_decoder_passthrough_guard
OUT=Path(tempfile.gettempdir())/"saturno23-native-eight"
ENGINE="60a7b7e9a39077b36f45057811abd6a833a168ef"

def run(args):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=300)
    if p.returncode:raise RuntimeError(f"{p.returncode}: {p.stderr[-1700:]}")
    return p.stdout

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()

def frames(path):
    raw=run(["ffmpeg","-v","error","-nostdin","-i",path,"-map","0:v:0","-an",
             "-c:v","rawvideo","-threads:v","1","-pix_fmt","yuv420p",
             "-fps_mode","passthrough","-f","framehash","-hash","sha256","-"])
    return [x.rsplit(",",1)[-1].strip() for x in raw.splitlines() if x and not x.startswith("#")]

def main():
    OUT.mkdir(exist_ok=True)
    report={"experiment":"SATURNO-23","status":"NOT_RUN","source_type":"synthetic; no audio","windows":[[20,26],[50,56]],"renders":{}}
    try:
        assert run(["git","-C",ROOT/"engine","rev-parse","HEAD"]).strip()==ENGINE
        report["engine"]=ENGINE
        source=OUT/"original.mp4";sparse=OUT/"sparse.mp4"
        run(["ffmpeg","-hide_banner","-v","error","-nostdin","-y","-f","lavfi",
             "-i","testsrc2=size=640x320:rate=30:duration=90",
             "-an","-c:v","libx264","-preset","ultrafast","-crf","24",
             "-g","60","-keyint_min","60","-sc_threshold","0","-bf","0",
             "-x264-params","open-gop=0","-threads:v","1","-pix_fmt","yuv420p",source])
        data=probe(str(source),packets=True)
        groups,selected,indices=choose_gops(data["packets"],[(20,26),(50,56)],1/30)
        assert len(selected)<len(groups)-10
        assert 13 in selected and 28 in selected
        selected=[i for i in selected if i not in (13,28)]
        assert len(selected)==8
        copy_sparse(str(source),str(sparse),data,groups,selected)
        info=probe(str(sparse),packets=True)
        expected=[data["packets"][i] for i in indices]
        assert len(expected)==len(info["packets"])
        assert all(all(a.get(k)==b.get(k) for k in ("data_hash","pts","dts")) for a,b in zip(expected,info["packets"]))
        report.update(original_bytes=source.stat().st_size,sparse_bytes=sparse.stat().st_size,
                      gops_total=len(groups),gops_retained=len(selected),
                      packets_total=len(data["packets"]),packets_retained=len(indices))
        sys.path.insert(0,str(ROOT/"engine"))
        from core.spherical_motion import run_reprojected_command
        shot={"yaw":164,"pitch":-17,"fov":90,"projection_preset":"linear",
              "movement":"settle","music_style":"animado","runtime_motion_enabled":True,"type":"right"}
        for label,path in (("A",source),("A_repeat",source),("B",sparse)):
            outputs=[]
            interventions=0
            for i,(begin,end) in enumerate(((20,26),(50,56))):
                out=OUT/f"{label}_{i}.mp4"
                n=(end-begin)*30
                command=["ffmpeg","-y","-hide_banner","-loglevel","error","-nostdin",
                    "-f","rawvideo","-pix_fmt","bgr24","-s","640x360","-r","30",
                    "-i","pipe:0","-an","-c:v","libx264","-preset","veryfast",
                    "-crf","19","-pix_fmt","yuv420p","-threads:v","1",
                    "-frames:v",str(n),out]
                with cpu_decoder_passthrough_guard() as evidence:
                    run_reprojected_command(command,str(path),(640,320),float(begin),n,shot,
                                          output_size=(640,360),fps=30,hardware_decode=False)
                assert len(evidence["interventions"])==1,{"label":label,"part":i,"evidence":evidence}
                interventions+=1
                outputs.append(out)
            segment_hashes=[frames(p) for p in outputs]
            assert all(len(h)==180 for h in segment_hashes)
            report["renders"][label]={"segments_sha256":[sha(p) for p in outputs],
                 "segment_sizes":[p.stat().st_size for p in outputs],
                 "frames_sha256":segment_hashes,"decoder_interventions":interventions}
            print("SATURNO23_RENDER="+json.dumps({"label":label,"frames":[len(x) for x in segment_hashes],
                  "interventions":interventions}),flush=True)
        base=report["renders"]["A"];repeat=report["renders"]["A_repeat"];packed=report["renders"]["B"]
        report["AA_exact"]=base["frames_sha256"]==repeat["frames_sha256"] and base["segments_sha256"]==repeat["segments_sha256"]
        report["AB_exact"]=base["frames_sha256"]==packed["frames_sha256"] and base["segments_sha256"]==packed["segments_sha256"]
        report["frames_total"]=sum(map(len,base["frames_sha256"]))
        report["status"]="NATIVE_EIGHT_GOP_AB_EXACT" if report["AA_exact"] and report["AB_exact"] and report["sparse_bytes"]<report["original_bytes"] else "NATIVE_EIGHT_GOP_MISMATCH"
    except Exception as exc:
        report.update(status="OPERATIONAL_ERROR",error=repr(exc))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(report,indent=2))
        print("SATURNO23_SUMMARY="+json.dumps({k:v for k,v in report.items() if k!="renders"},separators=(",",":")),flush=True)
    return 0 if report["status"]=="NATIVE_EIGHT_GOP_AB_EXACT" else 1
if __name__=="__main__":raise SystemExit(main())
