"""U21 real local Companion render from an authenticated-owner U20 descriptor.

One fixture *per Python process*, separate HOME and local HTTP port. GitHub
runs two in parallel to validate independent local renderers, NOT separate
physical machines, remote GCP or real Google sessions.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"companion"))
from test_local_video import install_layout, fingerprint
from urano.companion_handoff import project_handoff
from urano.project_catalog import ProjectCatalog

ORIGIN="http://127.0.0.1:8101"


def ff(*args):
    p=subprocess.run(["ffmpeg","-hide_banner","-v","error","-y",*args],
                     capture_output=True,text=True,timeout=120)
    if p.returncode:
        raise RuntimeError("Local synthetic FFmpeg fixture failed")


def http_post(url, data, *, origin=ORIGIN):
    request=Request(url,data=json.dumps(data).encode(),headers={
        "Origin":origin,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(request,timeout=45) as r:
            return r.status,json.loads(r.read())
    except HTTPError as exc:
        return exc.code,json.loads(exc.read())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--owner",choices=("alice","bob"),required=True)
    parser.add_argument("--u22-handoff",type=Path,
                        help="Use only the actual U20 Stage-DONE authorized handoff")
    args=parser.parse_args()
    root=args.output.resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("Use empty, disposable output for native test")
    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="urano-u21-") as temp:
        scratch=Path(temp)
        original=scratch/"originals"/"camera-original.mp4"
        original.parent.mkdir()
        chosen=scratch/"chosen-project"
        chosen.mkdir()
        ff("-f","lavfi","-i","testsrc2=size=640x360:rate=24:duration=5",
           "-c:v","libx264","-preset","ultrafast","-threads","1",
           "-pix_fmt","yuv420p",str(original))
        master=chosen/("montara-render-audio-"+uuid.uuid4().hex+".audio")
        ff("-f","lavfi","-i","sine=frequency=330:duration=5",
           "-ar","48000","-f","wav",str(master))
        home=scratch/"companion"
        home.mkdir()
        target,sha=install_layout(home)
        # Companion creates the server and the job manager in this isolated
        # client process. No GCP endpoint or files from any other owner.
        os.environ["MONTARA_COMPANION_HOME"]=str(home)
        os.environ["MONTARA_COMPANION_ROOTS"]=str(original.parent)
        spec=importlib.util.spec_from_file_location(
            "urano_u21_private_companion_"+args.owner,ROOT/"companion"/"companion.py")
        helper=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        local_id="b"*16
        helper.projects[local_id]=chosen
        identity={"name":original.name,"size":original.stat().st_size,
                  "fingerprint":fingerprint(original)}
        lookup=hashlib.sha256(
            f"{identity['name']}|{identity['size']}|{identity['fingerprint']}".encode()
        ).hexdigest()[:24]
        helper.sources[lookup]=original

        if args.u22_handoff:
            # This plan was fetched via owner-authorized HTTP after U20's
            # real pinned Docker Engine reported Ingest DONE. Companion only
            # sees this pathless JSON, never Docker paths/media/Google secrets.
            envelope=json.loads(args.u22_handoff.read_text(encoding="utf-8"))
            if set(envelope)!={"owner","plan"} or envelope["owner"]!=args.owner:
                raise ValueError("Handoff belongs to another owner")
            plan=envelope["plan"]
        else:
            catalog=ProjectCatalog(scratch/"catalog.sqlite3")
            owner="synthetic-owner-"+args.owner
            project=catalog.create(owner,"U21 owned edit")
            catalog.save_recipe(owner,project.id,{
                "urano_edits_v1":{"cuts":[
                    {"source_slot":0,"start_ms":500,"end_ms":2500}
                ]}},expected_revision=0)
            plan=project_handoff(catalog,owner,project.id)
        payload={
            "plan":plan,"project":local_id,"master":master.name,
            "originals":[{"source":0,"original":identity}],
            "branding":"none","name":"U21 native handoff",
        }
        server=ThreadingHTTPServer(("127.0.0.1",0),helper.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f"http://127.0.0.1:{server.server_port}"
        try:
            # Unknown/foreign origin and changed fingerprints must fail before
            # starting a render job or reading an original path from the wire.
            denied,_=http_post(base+"/video-renders/handoff",payload,
                               origin="https://unrelated.example")
            assert denied==403,denied
            wrong=json.loads(json.dumps(payload))
            wrong["originals"][0]["original"]["fingerprint"]="0"*64
            bad,reason=http_post(base+"/video-renders/handoff",wrong)
            assert bad==400,(bad,reason)
            assert len(helper.video_jobs.jobs)==0

            accepted,body=http_post(base+"/video-renders/handoff",payload)
            assert accepted==202,(accepted,body)
            assert body["local_originals"] is True
            token=body["id"]
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                with urlopen(Request(base+"/video-renders/"+token,
                                     headers={"Origin":ORIGIN}),timeout=8) as r:
                    status=json.loads(r.read())
                if status["status"] in ("ready","failed","cancelled"):
                    break
                time.sleep(.3)
            assert status["status"]=="ready",status
            output=helper.video_jobs.output(token)
            assert output.is_file() and output.stat().st_size>0
            manifest=json.loads((chosen/".montara-renders"/token/"render.json").read_text())
            assert Path(manifest["source_files"]["0"]).resolve()==original.resolve()
            assert manifest["recipe"]["segments"][0]["clip_start_sec"]==.5
            # The paths are written only in Companion's local render manifest.
            assert "source_files" not in json.dumps(plan)
            assert str(original) not in json.dumps(plan)
            stream=json.loads(subprocess.check_output([
                "ffprobe","-v","error","-show_streams","-of","json",str(output)],
                timeout=30))
            video=next(s for s in stream["streams"] if s["codec_type"]=="video")
            assert video["width"]>0 and video["height"]>0
            assert any(s["codec_type"]=="audio" for s in stream["streams"])
            subprocess.run(["ffmpeg","-v","error","-i",str(output),
                            "-f","null","-"],check=True,timeout=60)
            downloaded=root/"final.mp4"
            with urlopen(Request(base+"/video-renders/"+token+"/file",
                                 headers={"Origin":ORIGIN}),timeout=90) as r:
                with downloaded.open("wb") as dest:
                    while True:
                        chunk=r.read(1<<20)
                        if not chunk:break
                        dest.write(chunk)
            assert downloaded.stat().st_size==output.stat().st_size
            result={
                "schema":"urano-u21-local-render-acceptance-v1",
                "handoff_from_actual_stage":bool(args.u22_handoff),
                "owner":args.owner,
                "passed":True,"native_mp4_bytes":downloaded.stat().st_size,
                "used_verified_local_original":True,
                "wrong_fingerprint_rejected":True,
                "foreign_origin_rejected":True,
                "cloud_original_upload":False,
                "server_remote":False,
                "separate_physical_clients":False,
            }
            (root/"summary.json").write_text(json.dumps(result,indent=2))
            print(json.dumps(result),flush=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__=="__main__":
    main()
