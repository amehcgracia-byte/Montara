"""U16C: two signed Google owners, concurrent actual Stage ingest, cancellation & reopening.

Only disposable GitHub Actions Docker runners. Not Companion or real Mac media.
Each container has its own /workspace and sees neither other owner's inputs.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from urano.container_isolation import isolated_container_command
from urano.google_oidc import verify_google_id_token
from urano.google_owner import GoogleOwnerStore
from urano.project_catalog import ProjectCatalog
from test_google_flow_contract import SignedFakeGoogle, CLIENT

NONCE = "urano-stage-acceptance-nonce-test"
RECOVER = """
import json, os, sys
from pathlib import Path
root=Path('/workspace')
os.environ['ZUCKER_DATA_ROOT']=str(root)
os.environ['ZUCKER_MIXER_STATE_ROOT']=str(root/'Mixer'/'state')
sys.path.insert(0,'/app/engine')
from server.api import create_app
project=root/'Projects'/'MediaIngest'
assert (project/'project.json').is_file()
client=create_app(project_path=str(project),dev=False).test_client()
r=client.get('/api/v1/project')
assert r.status_code==200,(r.status_code,r.get_json())
state=client.application.config.get('ZUCKER_STATE')
loaded=getattr(getattr(state,'project',None),'folder',None)
assert loaded is not None and Path(loaded).resolve()==project.resolve()
print(json.dumps({'reopened':True,'project_path_verified':True}),flush=True)
"""


def check(result, label):
    if result.returncode:
        raise AssertionError(label + ": " + result.stderr[-1800:] + result.stdout[-1200:])
    return result.stdout


def run_container(image: str, workspace: Path, name: str, *, hold: bool = False):
    command = isolated_container_command(
        image=image, name=name, workspace=workspace,
        command=["python", "-u", "/app/tests/urano_two_owner_stage_in_container.py", "/workspace"],
        memory_mb=2560, cpus=2.0)
    # Environment values added by trusted test driver before the pinned image,
    # never taken from an HTTP request. No network, privileged mount or socket.
    if hold:
        image_position = command.index(image)
        command[image_position:image_position] = ["--env", "URANO_TEST_HOLD_AFTER_SUBMIT=1"]
    return command


def make_workspace(root: Path, owner: str):
    directory = root / owner
    directory.mkdir(mode=0o777)
    directory.chmod(0o777)
    (directory / "Projects").mkdir(mode=0o777)
    (directory / "Projects").chmod(0o777)
    return directory


def make_verified_owners(root: Path):
    provider = SignedFakeGoogle()
    owners = GoogleOwnerStore(root / "google-owners.sqlite3")
    catalog = ProjectCatalog(root / "catalog.sqlite3")
    mapping = {}
    for person in ("alice", "bob"):
        provider.sub, provider.email = "synthetic-sub-" + person, person + "@example.test"
        identity = verify_google_id_token(
            provider.token(NONCE), client_id=CLIENT, expected_nonce=NONCE,
            jwks=provider.jwks())
        mapping[person] = owners.resolve_beta_owner(
            identity, allowed_emails=frozenset({"alice@example.test", "bob@example.test"}))
        catalog.create(mapping[person], "MediaIngest")
    assert mapping["alice"] != mapping["bob"]
    assert len(catalog.list_for(mapping["alice"])) == 1
    assert len(catalog.list_for(mapping["bob"])) == 1
    return mapping


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Disposable GitHub Actions only, never JM/FER host")
    image = os.environ["URANO_TEST_IMAGE_ID"]
    with tempfile.TemporaryDirectory(prefix="urano-u16c-") as tmp:
        root = Path(tmp)
        try:
            owners = make_verified_owners(root)
            a = make_workspace(root, "alice")
            b = make_workspace(root, "bob")
            # Two REAL Stage ingest jobs, concurrently. Not merely opening projects.
            with ThreadPoolExecutor(max_workers=2) as pool:
                fa = pool.submit(subprocess.run, run_container(image, a, "urano-u16c-stage-alice"),
                                 capture_output=True, text=True, timeout=370)
                fb = pool.submit(subprocess.run, run_container(image, b, "urano-u16c-stage-bob"),
                                 capture_output=True, text=True, timeout=370)
                results = [fa.result(timeout=390), fb.result(timeout=390)]
            summaries = []
            for person, workspace, result in zip(("alice", "bob"), (a, b), results):
                output = check(result, person + " actual Stage ingest")
                summaries.append(json.loads([line for line in output.splitlines()
                                             if line.startswith("{")][-1]))
                assert summaries[-1]["passed"] and summaries[-1]["engine_stage"] == "ingest"
                project = workspace / "Projects" / "MediaIngest"
                assert (project / "project.json").is_file()
                assert (project / "inputs" / "camera-a.mp4").is_file()
                assert not (workspace / "Projects" / "BobProject").exists()
                assert not (workspace / "Projects" / "AliceProject").exists()
            # A third disposable Stage job is cancelled deliberately after 202,
            # while Bob's successful media/project stays untouched.
            cancelled = make_workspace(root, "alice-cancel")
            name = "urano-u16c-stage-cancel"
            cmd = run_container(image, cancelled, name, hold=True)
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            marker = cancelled / "stage-submitted.marker"
            try:
                deadline = time.monotonic() + 170
                while not marker.is_file() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.2)
                assert marker.is_file(), "Did not reach real Stage 202 before cancellation"
                removed = subprocess.run(["docker", "rm", "-f", name],
                                         capture_output=True, text=True, timeout=25)
                assert removed.returncode == 0, removed.stderr
                process.wait(timeout=15)
                assert process.returncode != 0, "Cancellation did not stop worker"
                absent = subprocess.run(["docker", "inspect", name],
                                        capture_output=True, timeout=10)
                assert absent.returncode != 0, "Cancelled container still exists"
                assert (cancelled / "Projects" / "MediaIngest" / "project.json").is_file()
            finally:
                if process.poll() is None:
                    subprocess.run(["docker", "rm", "-f", name],
                                   capture_output=True, timeout=20)
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout: process.stdout.close()
                if process.stderr: process.stderr.close()

            # Project reopening validates durable metadata; it does NOT claim
            # that an interrupted ingest/export automatically resumes.
            for person, workspace in (("alice", a), ("bob", b), ("cancelled", cancelled)):
                recover = isolated_container_command(
                    image=image, name="urano-u16c-reopen-" + person,
                    workspace=workspace, command=["python", "-c", RECOVER],
                    memory_mb=1536, cpus=1.0)
                recovered = subprocess.run(recover, capture_output=True, text=True, timeout=120)
                output = check(recovered, person + " reopen after cancellation")
                assert '"reopened": true' in output, output[-800:]
            assert (b / "Projects" / "MediaIngest" / "inputs" / "master.wav").is_file()
            print(json.dumps({
                "passed": True,
                "verified_google_owner_count": len(owners),
                "stage_concurrent_ingest_successes": len(summaries),
                "independent_engine_containers": True,
                "cross_owner_media_filesystem_isolated": True,
                "cancelled_stage_after_accepted": True,
                "cancelled_worker_removed": True,
                "projects_reopened": 3,
                "ingest_resume_after_cancel_verified": False,
                "concurrent_full_stage_export": False,
                "companion_two_user_render": False,
            },sort_keys=True),flush=True)
        finally:
            # Reclaim only CI-generated synthetic data inside disposable runner.
            subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(root)],
                           capture_output=True, timeout=30)


if __name__ == "__main__":
    main()
