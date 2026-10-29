"""SATURNO-20: controlled long-source sparse-GOP measurement (not a full edit).

Generate original 90s synthetic 360-like H.264 clip with 2s closed GOP;
keep windows only at 20-26s and 50-56s plus first/last GOP; compare exact
decoder BGR frames using the same passthrough control verified in SAT-16.
"""
import hashlib,json,subprocess,tempfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.saturno_10.packet_preflight import probe,choose_gops,copy_sparse

OUT=Path(tempfile.gettempdir())/"saturno20-selective"
def execute(cmd):
    p=subprocess.run(list(map(str,cmd)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError(p.stderr.decode(errors="replace")[-1800:])
    return p.stdout
def digest(b): return hashlib.sha256(b).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    result={"experiment":"SATURNO-20","status":"NOT_RUN","scope":"synthetic long-source sparse GOP transport preflight"}
    try:
        src=OUT/"original.mp4";dst=OUT/"sparse.mp4"
        # Closed GOP without B frames, fixed 30fps timestamp and deterministic single-thread encoder.
        execute(["ffmpeg","-hide_banner","-v","error","-nostdin","-y","-f","lavfi",
                 "-i","testsrc2=size=640x320:rate=30:duration=90",
                 "-an","-c:v","libx264","-preset","ultrafast","-crf","24","-g","60",
                 "-keyint_min","60","-sc_threshold","0","-bf","0","-x264-params","open-gop=0",
                 "-threads:v","1","-pix_fmt","yuv420p",src])
        a=probe(str(src),packets=True)
        windows=[(20.0,26.0),(50.0,56.0)]
        groups,selected,indices=choose_gops(a["packets"],windows,1/30)
        assert len(groups)>=40 and len(selected)<len(groups)-10,(len(groups),selected)
        command=copy_sparse(str(src),str(dst),a,groups,selected)
        b=probe(str(dst),packets=True)
        expected=[a["packets"][i] for i in indices]
        assert len(expected)==len(b["packets"])
        assert all(all(x.get(k)==y.get(k) for k in ("data_hash","pts","dts"))
                   for x,y in zip(expected,b["packets"])),"Retained packet payload or timestamps altered"
        comparisons=[]
        for begin,end in windows:
            hashes=[]
            for path in [src,dst]:
                raw=execute(["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                    "-threads","2","-ss",str(begin),"-i",path,
                    "-vf","fps=30,format=bgr24","-an",
                    "-frames:v",str(round((end-begin)*30)),
                    "-fps_mode","passthrough","-f","rawvideo","pipe:1"])
                hashes.append((digest(raw),len(raw)))
            comparisons.append({"start":begin,"end":end,"sha256_A":hashes[0][0],
                "sha256_B":hashes[1][0],"same":hashes[0]==hashes[1],
                "bytes_decoded_A":hashes[0][1],"bytes_decoded_B":hashes[1][1]})
        original_payload=sum(int(p["size"]) for p in a["packets"])
        retained_payload=sum(int(p["size"]) for p in expected)
        result.update(source_bytes=src.stat().st_size,packet_bytes=original_payload,
          packaged_bytes=dst.stat().st_size,retained_packet_bytes=retained_payload,
          gops_total=len(groups),gops_selected=len(selected),selected_indices=selected,
          source_packets=len(a["packets"]),retained_packets=len(b["packets"]),
          retained_packet_exact=True,windows=comparisons,
          container_bytes_saved=src.stat().st_size-dst.stat().st_size,
          payload_bytes_saved=original_payload-retained_payload,
          ffmpeg_command=command,
          limitations="Synthetic source with no audio, no color samples, no native Zucker render, no transfer. Not a production proof.")
        result["status"]="SPARSE_GOP_WINDOWS_EXACT" if all(c["same"] for c in comparisons) and result["container_bytes_saved"]>0 else "SPARSE_GOP_GATE_FAILED"
    except Exception as e:result.update(status="OPERATIONAL_ERROR",error=repr(e))
    finally:
        (OUT/"REPORT.json").write_text(json.dumps(result,indent=2)+"\n")
        print("SATURNO20_SUMMARY="+json.dumps({k:v for k,v in result.items() if k not in ("ffmpeg_command","selected_indices")},separators=(",",":")),flush=True)
    return 0 if result["status"]=="SPARSE_GOP_WINDOWS_EXACT" else 1
if __name__=="__main__":raise SystemExit(main())
