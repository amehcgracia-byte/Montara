"""Run a safe, isolated Montara CPU/NVENC smoke and capture machine/build identity."""
import argparse, hashlib, json, os, platform, subprocess, tempfile, time
from pathlib import Path

def call(cmd, timeout=40):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        return {"ok":p.returncode==0,"output":p.stdout[-1000:],"error":p.stderr[-800:]}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"ok":False,"error":type(e).__name__}

def sha(repo):
    r=call(["git","-C",str(repo),"rev-parse","HEAD"],5)
    s=r.get("output","").strip()
    return s if r["ok"] and len(s)==40 and all(c in "abcdef0123456789" for c in s) else None

def run(repo,seconds=2,gpu=False):
    if not 1<=seconds<=10: raise ValueError("seconds must be 1..10")
    root=Path(repo).resolve()
    def cgroup(k):
        try: return (Path("/sys/fs/cgroup")/k).read_text().strip()
        except OSError: return None
    result={"schema":"montara-cloud-lab-v1",
      "scope":"synthetic hardware smoke; not full Montara E2E",
      "system":{"os":platform.system(),"arch":platform.machine(),"python":platform.python_version(),
                "cpu_count":os.cpu_count(),"cpu_max":cgroup("cpu.max"),"memory_max":cgroup("memory.max")},
      "git":{"montara":sha(root),"engine":sha(root/"engine"),"mixer":sha(root/"mixer")},
      "ffmpeg":call(["ffmpeg","-version"],10).get("output","").splitlines()[:1],
      "nvidia_smi":call(["nvidia-smi","--query-gpu=name,memory.total,driver_version","--format=csv,noheader"],10).get("output","").strip() or None,
      "tests":{}}
    with tempfile.TemporaryDirectory(prefix="montara-qa-") as folder:
        for encoder in (["libx264","h264_nvenc"] if gpu else ["libx264"]):
            path=Path(folder)/(encoder+".mp4")
            cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y","-f","lavfi","-i",
                 f"testsrc2=size=640x360:rate=30:duration={seconds}","-an","-c:v",encoder,
                 "-pix_fmt","yuv420p",str(path)]
            start=time.perf_counter(); item=call(cmd,max(30,seconds*12))
            item.pop("output",None);item["wall_sec"]=round(time.perf_counter()-start,4)
            if item["ok"]:
                decoded=call(["ffmpeg","-v","error","-xerror","-nostdin","-i",str(path),"-f","null","-"])
                probed=call(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
                             "stream=codec_name,width,height,nb_frames","-of","json",str(path)])
                try:
                    stream=json.loads(probed["output"])["streams"][0]
                    valid=stream["codec_name"]=="h264" and stream["width"]==640
                except (ValueError,KeyError,IndexError): valid=False
                item.update({"ok":bool(decoded["ok"] and valid),"decoded":decoded["ok"],
                             "bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
            result["tests"][encoder]=item
    result["cpu_ready"]=result["tests"]["libx264"]["ok"]
    result["nvenc_ready"]=result["tests"].get("h264_nvenc",{}).get("ok") if gpu else None
    result["safety"]="Temporary synthetic media only; no cloud allocation or original uploads"
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--seconds",type=int,default=2)
    p.add_argument("--gpu",action="store_true")
    a=p.parse_args()
    data=run(a.repo,a.seconds,a.gpu)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,indent=2)+"\n")
    print(json.dumps({"cpu_ready":data["cpu_ready"],"nvenc_ready":data["nvenc_ready"]}))
    raise SystemExit(0 if data["cpu_ready"] else 1)
