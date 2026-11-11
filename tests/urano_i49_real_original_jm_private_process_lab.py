"""I49: complete Chema app/Engine inside a separate private child process.

Operator-only Linux lab: local per-owner WSGI and Stage status sockets,
real original JM upload and first draft, pinned Engine, synthetic FFmpeg MP4.
No Google session, root privileges, cloud service or live media.
"""
import argparse
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT = "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"


def child_worker(bundle, checkout, data, queue):
    try:
        from urano.full_jm_worker import serve_original_jm_worker
        serve_original_jm_worker(
            engine_root=Path(bundle), jm_root=Path(checkout),
            data_root=Path(data), project_id=PROJECT, generation=7,
            on_ready=lambda: queue.put({"ready": True, "pid": os.getpid()}),
        )
    except BaseException as exc:
        queue.put({"error": type(exc).__name__, "message": str(exc)[:250]})
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute:
        parser.error("Opt-in --execute required")
    bundle=args.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles") or len(bundle.name)!=47
            or not bundle.name.startswith("engine-")
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Invalid pinned Engine")
    checkout=Path(__file__).resolve().parents[1]
    if not (checkout/"app.py").is_file() or not (checkout/"web/montara.js").is_file():
        parser.error("Requires original JM product checkout")
    sys.path[:0]=[str(checkout),str(bundle/"site"),str(bundle/"app"),
                  str(bundle/"engine")]
    from core.project import new_project_document
    from urano.private_jm_wsgi_socket import (
        VerifiedJMUnixConnection,pinned_jm_static_assets,SOCKET_FILE
    )
    from urano.private_stage_unix_transport import SOCKET_NAME

    with tempfile.TemporaryDirectory(prefix="montara-i49-real-worker-") as tmp:
        root=Path(tmp)
        data=root/"isolated-owner-worker"
        data.mkdir(mode=0o700)
        folder=data/"Projects"/PROJECT
        folder.mkdir(parents=True)
        (folder/"project.json").write_text(json.dumps(new_project_document(PROJECT)))
        mp4=root/"synthetic-camera.mp4"
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=640x360:rate=12:duration=3",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            str(mp4),
        ],check=True,stderr=subprocess.PIPE,timeout=45)
        ctx=multiprocessing.get_context("fork")
        queue=ctx.Queue()
        proc=ctx.Process(target=child_worker,args=(
            str(bundle),str(checkout),str(data),queue),daemon=True)
        proc.start()
        try:
            startup=queue.get(timeout=25)
            if startup.get("ready") is not True or startup.get("pid")!=proc.pid:
                raise RuntimeError("Real JM worker not ready: "+str(startup))
            if not (data/SOCKET_FILE).is_socket() or not (data/SOCKET_NAME).is_socket():
                raise RuntimeError("Owner JM HTTP and status sockets missing")
            marker=json.loads((data/"ready.json").read_text())
            if marker.get("folder")!=PROJECT:
                raise RuntimeError("Owner worker readiness wrong project")
            with VerifiedJMUnixConnection(
                data/SOCKET_FILE,expected_pid=proc.pid,
                expected_uid=os.getuid(),
                approved_assets=pinned_jm_static_assets(checkout/"web"),
            ) as http:
                code,_,html=http.get_safe_read("/")
                if code!=200 or b'data-platform="youtube"' not in html:
                    raise RuntimeError("Original JM editor HTML unavailable")
                code,_,javascript=http.get_safe_read("/montara.js")
                if code!=200 or len(javascript)<1000:
                    raise RuntimeError("Original JM JavaScript unavailable")
                http.request("POST","/api/v1/wizard/upload",
                    body=mp4.read_bytes(),headers={
                        "Content-Type":"application/octet-stream",
                        "X-Zucker-Filename":"synthetic-camera.mp4",
                    })
                upload=http.getresponse()
                if upload.status!=200:
                    raise RuntimeError("JM original upload failed")
                result=json.loads(upload.read())
                sources=result.get("videos") or []
                if len(sources)!=1:
                    raise RuntimeError("JM classified synthetic video as unusable")
                video_path=sources[0]["path"]
                if not Path(video_path).is_relative_to(data/"WizardUploads"):
                    raise RuntimeError("JM upload escaped Owner worker")
                new_status,_,_=http.post_first_stage_json(
                    "/api/v1/wizard/projects/new",{})
                draft_status,_,body=http.post_first_stage_json(
                    "/api/v1/wizard/draft",{
                        "name":"Separate process Stage",
                        "platform":"youtube","project_id":None,
                        "master":"","audio_paths":[],"videos":[video_path],
                    })
                if (new_status!=200 or draft_status!=200
                        or json.loads(body).get("project_id")!=str(folder)):
                    raise RuntimeError("Original JM draft lost Owner UUID")
            print(json.dumps({
                "separate_private_worker_process":True,
                "real_original_chema_editor":True,
                "real_pinned_engine":True,
                "real_ffmpeg_video_upload":True,
                "private_unix_http_and_stage_sockets":True,
                "owner_uuid_preserved":True,
                "cloud_deployment_changed":False,
                "systemd_dynamic_uid_tested":False,
                "google_login_live_tested":False,
                "windows_companion_final_mp4_tested":False,
            },sort_keys=True))
        finally:
            if proc.is_alive():
                proc.terminate()
            proc.join(timeout=8)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=4)
            queue.close()


if __name__=="__main__":
    main()
