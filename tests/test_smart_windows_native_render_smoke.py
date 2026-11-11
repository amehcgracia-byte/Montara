"""Windows acceptance: Chema native Stage Engine produces a real local MP4.

Run against the unpacked SMART ZIP after its native renderer installer succeeds.
Uses only two seconds of generated FFmpeg synthetic media and a temp folder.
No cloud/login and no user's source files.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid


ENGINE = "b867b3c72af8fe4685b487bcf1e09ffcc2a7c82b"


def run(*cmd, timeout=40):
    return subprocess.run(cmd,check=True,capture_output=True,
                          timeout=timeout).stdout


def sha_edges(path: Path) -> str:
    with path.open("rb") as fd:
        first=fd.read(65536)
        fd.seek(max(0,path.stat().st_size-65536))
        last=fd.read(65536)
    return hashlib.sha256(first+last).hexdigest()


def main():
    package=Path(os.environ["MONTARA_SMART_PACKAGE_ROOT"])
    home=Path(os.environ["LOCALAPPDATA"])/"MontaraSMARTBeta"
    sys.path.insert(0,str(package))
    from video_jobs import VideoJobs
    with tempfile.TemporaryDirectory(prefix="montara-windows-native-") as tmp:
        root=Path(tmp)
        originals=root/"originals"
        originals.mkdir()
        source=originals/"camera-original.mp4"
        project=root/"Montara"/"Smart Windows render"
        project.mkdir(parents=True)
        master=project/f"montara-render-audio-{uuid.uuid4().hex}.audio"
        run("ffmpeg","-y","-v","error","-f","lavfi","-i",
            "testsrc2=size=640x360:rate=24:duration=2.5",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            str(source))
        run("ffmpeg","-y","-v","error","-f","lavfi","-i",
            "sine=frequency=440:sample_rate=48000:duration=2.5",
            "-c:a","pcm_s16le","-f","wav",str(master))
        src_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        user_project="a"*16
        original={
            "name":source.name,"size":source.stat().st_size,
            "fingerprint":sha_edges(source),
        }
        recipe={
            "version":1,"engine":ENGINE,"platform":"youtube",
            "sources":[{"key":0}],
            "segments":[{"source":0,"clip_start_sec":0,
                         "duration_sec":2.0,"master_start_sec":0,
                         "video_light":{"auto":False,"light":0,"shadows":0}}],
        }
        manager=VideoJobs(home)
        assert manager.runtime()=={"engine":ENGINE},manager.runtime()
        token=manager.start({
            "project":user_project,"master":master.name,
            "recipe":recipe,"originals":[{"source":0,"original":original}],
            "branding":"none","name":"Montara SMART Windows proof",
        },{user_project:project},lambda identity: source)
        deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            status=manager.status(token)
            if status["status"] in ("ready","failed","cancelled"):break
            time.sleep(0.5)
        else:
            manager.cancel(token)
            raise RuntimeError("Windows native render exceeded 150 second proof limit")
        if status["status"]!="ready":
            log=project/".montara-renders"/token/"render.log"
            diagnostics=log.read_text(encoding="utf-8",errors="replace")[-5000:] if log.exists() else "(no log)"
            raise RuntimeError("Windows native renderer failed: "+str(status)+"\n"+diagnostics)
        final=manager.output(token)
        assert final and final.is_file() and final.stat().st_size>100_000
        ffprobe=json.loads(run("ffprobe","-v","error","-show_streams",
                                "-show_format","-of","json",str(final)))
        streams=ffprobe["streams"]
        video=next(s for s in streams if s["codec_type"]=="video")
        assert (video["width"],video["height"])==(1920,1080),video
        assert hashlib.sha256(source.read_bytes()).hexdigest()==src_hash
        assert not (home/"originals").exists()
        assert final.parent==project
        print(json.dumps({
            "SMART_WINDOWS_NATIVE_REAL_MP4_PASS":True,
            "source_untouched":True,
            "originals_uploaded":False,
            "rendered_resolution":"1920x1080",
            "mp4_bytes":final.stat().st_size,
            "saved_inside_selected_project":True,
            "engine":ENGINE,
        },sort_keys=True),flush=True)


if __name__=="__main__":
    main()
