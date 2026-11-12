"""I44 isolated FULL original JM Stage first draft via actual Unix HTTP POST.

Chema's ORIGINAL Montara app and pinned real Engine; no alternative editor.
The OwnerFirstStageWizard WSGI adapter preserves the authenticated project
UUID when original browser code calls /wizard/projects/new then /wizard/draft.
Synthetic MP4 only. Still NOT an authenticated browser or production broker.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--bundle",type=Path,required=True)
    arg.add_argument("--execute",action="store_true")
    a=arg.parse_args()
    if not a.execute:
        arg.error("Operator --execute required")
    bundle=a.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles")
            or len(bundle.name)!=47
            or not bundle.name.startswith("engine-")
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        arg.error("Invalid immutable real Engine")
    checkout=Path(__file__).resolve().parents[1]
    if not (checkout/"app.py").is_file() or not (checkout/"web/index.html").is_file():
        arg.error("Complete original JM product checkout required")
    sys.path[:0]=[str(checkout),str(bundle/"site"),
                  str(bundle/"app"),str(bundle/"engine")]
    from app import create_montara_app
    from core.project import new_project_document
    from urano.owner_first_stage_wizard import OwnerFirstStageWizard
    from urano.private_jm_wsgi_socket import (
        create_private_jm_wsgi_server,VerifiedJMUnixConnection,
        pinned_jm_static_assets,
    )

    with tempfile.TemporaryDirectory(prefix="montara-i44-stage-socket-") as temporary:
        root=Path(temporary)
        data=root/"owner-worker"
        data.mkdir(mode=0o700)
        uuid="7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
        folder=data/"Projects"/uuid
        folder.mkdir(parents=True)
        (folder/"project.json").write_text(
            json.dumps(new_project_document(uuid)),encoding="utf-8")
        (data/"WizardUploads").mkdir(exist_ok=True)
        proxy=data/"WizardUploads"/"synthetic-proxy.mp4"
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=320x180:rate=12:duration=2",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            "-c:a","aac","-shortest",str(proxy),
        ],check=True,stderr=subprocess.PIPE,timeout=45)
        app=create_montara_app(data,samples=False)
        opened=app.test_client().post(
            "/api/v1/wizard/projects/open",json={"path":str(folder)})
        if opened.status_code!=200:
            raise RuntimeError("Original Engine did not open Owner UUID")
        wsgi=OwnerFirstStageWizard(app,owner_project_folder=folder)
        server,sock=create_private_jm_wsgi_server(wsgi,data)
        runner=threading.Thread(target=server.serve_forever,daemon=True)
        runner.start()
        result={}
        try:
            with VerifiedJMUnixConnection(
                sock,expected_pid=os.getpid(),expected_uid=os.getuid(),
                approved_assets=pinned_jm_static_assets(checkout/"web"),
            ) as conn:
                html_status,_,html=conn.get_safe_read("/")
                if html_status!=200 or b'data-platform="youtube"' not in html:
                    raise RuntimeError("Original editor unavailable over Unix")
                new_status,_,_=conn.post_first_stage_json(
                    "/api/v1/wizard/projects/new",{})
                draft_status,_,body=conn.post_first_stage_json(
                    "/api/v1/wizard/draft",{
                        "name":"JM Stage over Unix", "platform":"youtube",
                        "project_id":None,"master":"",
                        "audio_paths":[],"videos":[str(proxy)],
                    })
                if new_status!=200 or draft_status!=200:
                    raise RuntimeError("Stage wizard failed via private Unix: "+
                                       str([new_status,draft_status,body[:250]]))
                result=json.loads(body)
                if result.get("project_id")!=str(folder):
                    raise RuntimeError("Original JM wizard escaped Owner UUID")
                again_status,_,_=conn.post_first_stage_json(
                    "/api/v1/wizard/projects/new",{})
                if again_status!=409:
                    raise RuntimeError("Existing project overwrite allowed")
            if sorted(p.name for p in (data/"Projects").iterdir()
                      if p.is_dir())!=[uuid]:
                raise RuntimeError("JM created a second Engine project")
        finally:
            server.shutdown()
            server.server_close()
            runner.join(timeout=5)
            sock.unlink(missing_ok=True)
        if runner.is_alive():
            raise RuntimeError("Original JM worker did not stop")
        print(json.dumps({
            "authentic_chema_editor_over_unix":True,
            "actual_ffmpeg_proxy_draft_over_unix":True,
            "original_jm_stage_endpoint_post":True,
            "owner_uuid_preserved":True,
            "second_internal_jm_project_created":False,
            "overwrite_denied":True,
            "external_browser_live":False,
            "google_login_this_lab":False,
            "companion_windows_mp4":False,
        },sort_keys=True))


if __name__=="__main__":
    main()
