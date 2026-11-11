"""I43 opt-in: ORIGINAL Chema Stage wizard draft with actual small MP4 proxy.

Demonstrates that POST /wizard/projects/new and /wizard/draft(project_id:null)
reuse the authorized Owner UUID, rather than creating another Engine project.
Synthetic 320x180 fixture only. No original user videos, login, or public HTTP.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",type=Path,required=True)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute:
        parser.error("Operator-only --execute required")
    bundle=args.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-")
            or len(bundle.name)!=47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Invalid pinned Engine")
    root=Path(__file__).resolve().parents[1]
    if not (root/"app.py").is_file() or not (root/"web/index.html").is_file():
        parser.error("Original Montara JM product checkout required")
    sys.path[:0]=[str(root),str(bundle/"site"),str(bundle/"app"),
                  str(bundle/"engine")]
    from app import create_montara_app
    from core.project import new_project_document
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from urano.owner_first_stage_wizard import OwnerFirstStageWizard

    with tempfile.TemporaryDirectory(prefix="montara-i43-owner-draft-") as temporary:
        temp=Path(temporary)
        private=temp/"private-jm"
        folder=private/"Projects"/"7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"
        folder.mkdir(parents=True)
        (folder/"project.json").write_text(
            json.dumps(new_project_document(folder.name)),encoding="utf-8")
        proxy=temp/"synthetic-proxy.mp4"
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=320x180:rate=12:duration=2",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v","libx264","-preset","ultrafast",
            "-pix_fmt","yuv420p","-c:a","aac","-shortest",str(proxy),
        ],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45)
        app=create_montara_app(private,samples=False)
        opened=app.test_client().post(
            "/api/v1/wizard/projects/open",json={"path":str(folder)})
        if opened.status_code!=200:
            raise RuntimeError("Original Engine refused owner project")
        browser=Client(OwnerFirstStageWizard(app,owner_project_folder=folder),Response)
        new=browser.post("/api/v1/wizard/projects/new",json={})
        draft=browser.post("/api/v1/wizard/draft",json={
            "name":"Lab original Stage draft", "platform":"youtube",
            "project_id":None,"videos":[str(proxy)],"master":"",
            "audio_paths":[],
        })
        if new.status_code!=200 or draft.status_code!=200:
            raise RuntimeError("Original Stage draft failed: "+str({
                "new":new.status_code,"draft":draft.status_code,
                "reason":draft.get_data(as_text=True)[:250],
            }))
        result=draft.get_json()
        if result["project_id"]!=str(folder):
            raise RuntimeError("Stage created a project outside Owner UUID")
        folders=sorted(p.name for p in (private/"Projects").iterdir() if p.is_dir())
        if folders!=[folder.name]:
            raise RuntimeError("Stage draft generated another JM project: "+str(folders))
        repeated_new=browser.post("/api/v1/wizard/projects/new",json={})
        if repeated_new.status_code!=409:
            raise RuntimeError("Existing saved Owner project was overwritten")
        print(json.dumps({
            "original_jm_stage_draft_real":True,
            "actual_ffmpeg_synthetic_proxy":True,
            "opened_owner_uuid_preserved":True,
            "additional_jm_folders_created":0,
            "accidental_new_overwrite_blocked":True,
            "original_media_uploaded":False,
            "google_browser_auth_checked":False,
            "companion_windows_mp4_checked":False,
        },sort_keys=True))


if __name__=="__main__":
    main()
