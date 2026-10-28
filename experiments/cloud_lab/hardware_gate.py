"""Offline hardware gate; advertised encoders do not imply working GPU runtime."""
import argparse,json,platform,subprocess,tempfile,time
from pathlib import Path

def run(argv,timeout=25):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
        return {"ok":p.returncode==0,"error":(p.stderr or "")[-700:] if p.returncode else ""}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {"ok":False,"error":type(exc).__name__}

def examine(binary="ffmpeg",seconds=2):
    if not 1<=seconds<=10: raise ValueError("seconds must be 1..10")
    r={"os":platform.system(),"arch":platform.machine(),"seconds":seconds,"tests":{}}
    with tempfile.TemporaryDirectory(prefix="montara-gate-") as directory:
        for encoder in ("libx264","h264_nvenc"):
            output=Path(directory)/(encoder+".mp4")
            argv=[binary,"-hide_banner","-loglevel","error","-nostdin","-y",
                  "-f","lavfi","-i",f"testsrc2=size=640x360:rate=24:duration={seconds}",
                  "-an","-c:v",encoder,"-pix_fmt","yuv420p",str(output)]
            started=time.perf_counter()
            result=run(argv,timeout=45)
            result["wall_seconds"]=round(time.perf_counter()-started,3)
            if result["ok"]:
                check=run([binary,"-v","error","-xerror","-i",str(output),"-f","null","-"])
                result["decode_verified"]=check["ok"]
                result["bytes"]=output.stat().st_size
                result["ok"]=result["ok"] and check["ok"]
            r["tests"][encoder]=result
    r["cpu_runtime_usable"]=r["tests"]["libx264"]["ok"]
    r["gpu_runtime_usable"]=r["tests"]["h264_nvenc"]["ok"]
    r["warning"]="Encode-only smoke; does not validate engine GPU use for v360, decode, audio or models."
    return r

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--ffmpeg",default="ffmpeg");p.add_argument("--seconds",type=int,default=2)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    r=examine(a.ffmpeg,a.seconds)
    print(json.dumps(r,indent=2))
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(r,indent=2)+"\n")
