"""I52 physical lab: Owner JM project survives process AND runtime-dir restart.

Runs original Chema Flask+Engine under two consecutive child processes using
one persistent Owner data folder and fresh per-generation Unix runtime sockets.
No root/systemd modifications, no live user videos and no cloud deployment.
"""
from __future__ import annotations
import argparse
import json
import multiprocessing
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT="7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"


def child(engine,jm,data,runtime,generation,queue):
    from urano.full_jm_worker import serve_original_jm_worker
    try:
        serve_original_jm_worker(
            engine_root=Path(engine),jm_root=Path(jm),
            data_root=Path(data),runtime_root=Path(runtime),
            project_id=PROJECT,generation=generation,
            on_ready=lambda:queue.put({"ready":True,"pid":os.getpid()}),
        )
    except BaseException as exc:
        queue.put({"error":type(exc).__name__,"message":str(exc)[:250]})
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute: parser.error("Operator-only --execute required")
    bundle=args.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-") or len(bundle.name)!=47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Pinned original Engine required")
    checkout=Path(__file__).resolve().parents[1]
    if not (checkout/"web/montara.js").is_file():
        parser.error("Original Chema product source checkout required")
    sys.path[:0]=[str(checkout),str(bundle/"site"),str(bundle/"app"),str(bundle/"engine")]
    from core.project import new_project_document
    from urano.private_jm_wsgi_socket import VerifiedJMUnixConnection, SOCKET_FILE
    ctx=multiprocessing.get_context("fork")
    with tempfile.TemporaryDirectory(prefix="montara-i52-owner-durable-") as tmp:
        root=Path(tmp)
        persistent=root/"durable-owner-state"
        persistent.mkdir(mode=0o700)
        folder=persistent/"Projects"/PROJECT
        folder.mkdir(parents=True)
        (folder/"project.json").write_text(json.dumps(new_project_document(PROJECT)))
        video=root/"synthetic-camera.mp4"
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=640x360:rate=12:duration=3",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            str(video),
        ],check=True,stderr=subprocess.PIPE,timeout=45)
        snapshots=[]
        for generation in (1,2):
            runtime=root/("runtime-"+str(generation))
            runtime.mkdir(mode=0o700)
            queue=ctx.Queue()
            proc=ctx.Process(target=child,args=(
                str(bundle),str(checkout),str(persistent),str(runtime),
                generation,queue),daemon=True)
            proc.start()
            try:
                ready=queue.get(timeout=25)
                if ready.get("ready") is not True or ready.get("pid")!=proc.pid:
                    raise RuntimeError("Original JM worker failed to start: "+str(ready))
                if not (runtime/SOCKET_FILE).is_socket():
                    raise RuntimeError("Worker generation has no Unix listener")
                with VerifiedJMUnixConnection(
                    runtime/SOCKET_FILE,expected_pid=proc.pid,
                    expected_uid=os.getuid(),
                ) as conn:
                    if generation==1:
                        conn.request("POST","/api/v1/wizard/upload",
                            body=video.read_bytes(),headers={
                                "Content-Type":"application/octet-stream",
                                "X-Zucker-Filename":"synthetic-camera.mp4"})
                        uploaded=conn.getresponse()
                        if uploaded.status!=200:
                            raise RuntimeError("Owner first upload failed")
                        found=json.loads(uploaded.read()).get("videos",[])
                        if len(found)!=1:
                            raise RuntimeError("Original JM Engine did not classify video")
                        path=found[0]["path"]
                        created,_,_=conn.post_first_stage_json(
                            "/api/v1/wizard/projects/new",{})
                        saved,_,data=conn.post_first_stage_json(
                            "/api/v1/wizard/draft",{
                                "name":"Persistent Stage","platform":"youtube",
                                "project_id":None,"videos":[path],
                                "master":"","audio_paths":[],
                            })
                        if (created!=200 or saved!=200
                                or json.loads(data).get("project_id")!=str(folder)):
                            raise RuntimeError("Stage first draft was not saved")
                    else:
                        replaced,_,_=conn.post_first_stage_json(
                            "/api/v1/wizard/projects/new",{})
                        if replaced!=409:
                            raise RuntimeError("Restart lost nonempty Owner Stage")
                    code,_,body=conn.get_safe_read("/api/v1/project")
                    if code!=200:
                        raise RuntimeError("Original project not reopened")
                    snapshots.append(json.loads(body))
            finally:
                if proc.is_alive(): proc.terminate()
                proc.join(timeout=8)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=4)
                queue.close()
        if not (folder/"project.json").is_file():
            raise RuntimeError("Owner project metadata lost after restart")
        if snapshots[0]!=snapshots[1]:
            raise RuntimeError("Original JM state changed or vanished after worker restart")
        print(json.dumps({
            "original_jm_and_real_engine":True,
            "separate_worker_generations":2,
            "same_owner_durable_state_root":True,
            "sockets_have_distinct_ephemeral_runtime_dirs":True,
            "stage_project_recovers_after_process_restart":True,
            "saved_project_not_overwritten":True,
            "root_broker_or_systemd_changed":False,
            "google_browser_tested":False,
            "windows_companion_tested":False,
        },sort_keys=True))


if __name__=="__main__":
    main()
