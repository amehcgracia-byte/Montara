"""Trusted test-only fixture. Prepare synthetic Engine media before U20 worker starts.

Runs only inside disposable Docker image on /workspace synthetic project.
Not an HTTP endpoint, production API, or permitted browser action.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    if sys.argv[1:] not in (["OwnedAlice"], ["OwnedBob"]):
        raise SystemExit("Synthetic owned test folder required")
    root=Path("/workspace")
    project=root/"Projects"/sys.argv[1]
    assert project.is_dir() and (project/"project.json").is_file()
    media=project/"inputs"
    media.mkdir(exist_ok=True)
    master=media/"master.wav"
    camera=media/"camera-a.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-f","lavfi","-i","anoisesrc=color=pink:seed=112:duration=7",
                    "-ar","48000",str(master)],check=True,timeout=60)
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                    "-f","lavfi","-i","testsrc2=size=320x180:rate=24:duration=7",
                    "-i",str(master),"-c:v","libx264","-preset","ultrafast",
                    "-threads","1","-pix_fmt","yuv420p","-c:a","aac",
                    "-shortest",str(camera)],check=True,timeout=80)
    os.environ["ZUCKER_DATA_ROOT"]=str(root)
    os.environ["ZUCKER_MIXER_STATE_ROOT"]=str(root/"Mixer"/"state")
    sys.path.insert(0,"/app/engine")
    from server.api import create_app
    client=create_app(project_path=str(project),dev=False).test_client()
    v=client.post("/api/v1/inputs/videos",json={"paths":[str(camera)]})
    a=client.post("/api/v1/inputs/master",json={"master":str(master)})
    assert v.status_code == 200, (v.status_code,v.get_json())
    assert a.status_code == 200, (a.status_code,a.get_json())
    print(json.dumps({"fixture_prepared":True,"local_media":True}),flush=True)


if __name__=="__main__":
    main()
