"""I50 opt-in two-Owner ORIGINAL JM editor lab, separate processes and UUIDs.

Checks that A's uploaded proxy/draft cannot be attached to B's Stage project.
Uses two isolated Python processes with distinct data roots but SAME lab UID.
This is not yet production systemd DynamicUser or real OAuth/Companion.
"""
import argparse
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
from pathlib import Path

A = "7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
B = "b6e40fcf-a923-494c-acaa-c5836da72e80"


def child(bundle, checkout, data, project_id, queue):
    from urano.full_jm_worker import serve_original_jm_worker
    def ready():
        queue.put({"id": project_id, "pid": os.getpid(), "ready": True})
    try:
        serve_original_jm_worker(
            engine_root=Path(bundle), jm_root=Path(checkout),
            data_root=Path(data), project_id=project_id,
            generation=1, on_ready=ready)
    except BaseException as exc:
        queue.put({"id":project_id,"error":type(exc).__name__,
                   "reason":str(exc)[:220]})
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",required=True,type=Path)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute:
        parser.error("--execute on isolated VM only")
    bundle=args.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-") or len(bundle.name)!=47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Pinned engine required")
    checkout=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(checkout),str(bundle/"site"),str(bundle/"app"),str(bundle/"engine")]
    from core.project import new_project_document
    from urano.private_jm_wsgi_socket import VerifiedJMUnixConnection,SOCKET_FILE

    with tempfile.TemporaryDirectory(prefix="montara-i50-owners-") as tmp:
        root=Path(tmp)
        jobs=[]
        ctx=multiprocessing.get_context("fork")
        queue=ctx.Queue()
        for project_id in (A,B):
            data=root/project_id
            data.mkdir(mode=0o700)
            folder=data/"Projects"/project_id
            folder.mkdir(parents=True)
            (folder/"project.json").write_text(
                json.dumps(new_project_document(project_id)))
            proc=ctx.Process(
                target=child,
                args=(str(bundle),str(checkout),str(data),project_id,queue),
                daemon=True)
            proc.start()
            jobs.append((project_id,data,proc))
        try:
            ready=[queue.get(timeout=30) for _ in jobs]
            if (set(item.get("id") for item in ready)!={A,B}
                    or any(item.get("ready") is not True for item in ready)):
                raise RuntimeError("Two private JM workers not ready: "+str(ready))
            for project_id,data,proc in jobs:
                if not proc.is_alive() or not (data/SOCKET_FILE).is_socket():
                    raise RuntimeError("Private JM process unexpectedly stopped")

            video=root/"synthetic-cam.mp4"
            subprocess.run([
                "ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i","testsrc2=size=640x360:rate=12:duration=3",
                "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
                str(video),
            ],check=True,stderr=subprocess.PIPE,timeout=45)
            sockets={project_id:VerifiedJMUnixConnection(
                data/SOCKET_FILE,expected_pid=proc.pid,
                expected_uid=os.getuid()) for project_id,data,proc in jobs}
            try:
                a=sockets[A]
                a.request("POST","/api/v1/wizard/upload",
                          body=video.read_bytes(),headers={
                              "Content-Type":"application/octet-stream",
                              "X-Zucker-Filename":"synthetic-cam.mp4"})
                upload=a.getresponse()
                if upload.status!=200:
                    raise RuntimeError("Owner A could not upload")
                result=json.loads(upload.read())
                paths=[v["path"] for v in result.get("videos",[])]
                if len(paths)!=1 or not Path(paths[0]).is_relative_to(root/A):
                    raise RuntimeError("Owner A media outside A")
                a.post_first_stage_json("/api/v1/wizard/projects/new",{})
                status,_,body=a.post_first_stage_json(
                    "/api/v1/wizard/draft",{
                        "project_id":None,"name":"Stage A","platform":"youtube",
                        "master":"","audio_paths":[],"videos":paths})
                if status!=200 or json.loads(body).get("project_id")!=str(root/A/"Projects"/A):
                    raise RuntimeError("Owner A Stage not saved")

                b=sockets[B]
                b.post_first_stage_json("/api/v1/wizard/projects/new",{})
                forbidden,_,_=b.post_first_stage_json(
                    "/api/v1/wizard/draft",{
                        "project_id":None,"name":"Stage B","platform":"youtube",
                        "master":"","audio_paths":[],"videos":paths})
                if forbidden!=400:
                    raise RuntimeError("Owner B accepted Owner A proxy")
                code,_,body=b.get_safe_read("/api/v1/project")
                if code!=200 or (json.loads(body).get("inputs") or {}).get("videos"):
                    raise RuntimeError("Owner B project was mutated")
            finally:
                for item in sockets.values():
                    item.close()
            print(json.dumps({
                "real_original_jm_workers":2,
                "different_owner_uuid_and_data_root":True,
                "owner_a_real_ffmpeg_proxy_and_stage":True,
                "owner_b_foreign_proxy_denied_http_400":True,
                "owner_b_project_unchanged":True,
                "separate_python_pids":True,
                "linux_dynamicuser_tested":False,
                "google_browser_login_tested":False,
                "windows_companion_tested":False,
            },sort_keys=True))
        finally:
            for _,_,proc in jobs:
                if proc.is_alive():
                    proc.terminate()
            for _,_,proc in jobs:
                proc.join(timeout=8)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=4)
            queue.close()


if __name__=="__main__":
    main()
