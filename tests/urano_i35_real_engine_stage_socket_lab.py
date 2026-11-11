"""Opt-in I35 actual Engine -> in-process private Stage Unix socket lab.

Requires a trusted, read-only, pinned Engine bundle. Creates ONLY a new
temporary project under /tmp; no network, Google sessions, systemd unit,
video upload, FFmpeg render or changes to production workspaces.

Run only on a prepared Linux lab with:
 /opt/.../python/bin/python3.11 tests/urano_i35_real_engine_stage_socket_lab.py \\
   --bundle /opt/montara/bundles/engine-<sha> --execute
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Requires explicit --execute")
    bundle = args.bundle.resolve(strict=True)
    if (bundle.parent != Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-")
            or len(bundle.name) != len("engine-") + 40
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])
            or not (bundle / "engine/server/api.py").is_file()
            or not (bundle / "site").is_dir()):
        parser.error("Not a pinned Engine bundle")
    repo_root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(repo_root), str(bundle / "site"), str(bundle / "app"),
                    str(bundle / "engine"), str(bundle)]
    from core.project import new_project_document
    from urano.engine_worker_process import make_engine_client
    from urano.private_stage_payload import private_stage_snapshot
    from urano.private_stage_unix_transport import (
        serve_stage_socket, SystemdUnixStageTransport, SOCKET_NAME,
    )
    from urano.restricted_systemd_broker import expected_cgroup

    unit = "montara-i24-job-" + uuid.uuid4().hex
    project = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="montara-i35-engine-") as temporary:
        root = Path(temporary)
        directory = root / unit
        folder = directory / "Projects" / project
        folder.mkdir(parents=True)
        (folder / "project.json").write_text(
            json.dumps(new_project_document(project)), encoding="utf-8")
        engine = make_engine_client(bundle / "engine", directory)
        opened = engine.post("/api/v1/wizard/projects/open",
                             json={"path": str(folder)})
        if opened.status_code != 200:
            raise RuntimeError("Real Engine project open denied")
        payload = private_stage_snapshot(engine, folder)
        ready = threading.Event()
        failures = []

        def worker():
            try:
                serve_stage_socket(
                    directory, project_id=project, generation=1,
                    read_snapshot=lambda: private_stage_snapshot(engine, folder),
                    trusted_broker_uid=os.getuid(), max_requests=1,
                    on_listening=ready.set,
                )
            except Exception as exc:
                failures.append(type(exc).__name__)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        if not ready.wait(timeout=8):
            raise RuntimeError("Isolated Stage IPC not ready")
        transport = SystemdUnixStageTransport(
            lambda name: {
                "ActiveState": "active", "ControlGroup": expected_cgroup(name),
                "MainPID": str(os.getpid()),
            },
            runtime_root=root,
        )
        result = transport.stage_snapshot(
            unit, project_id=project, generation=1)
        thread.join(timeout=8)
        if thread.is_alive() or failures:
            raise RuntimeError("Private Unix worker did not exit cleanly")
        if result != payload or (directory / SOCKET_NAME).exists():
            raise RuntimeError("Real Engine snapshot or socket cleanup mismatch")
        print(json.dumps({
            "real_engine_opened": True,
            "unix_socket_real": True,
            "stage_snapshot_verified": True,
            "engine_bundle": bundle.name,
            "stages": result["stages"],
            "camera_count": result["camera_count"],
            "production_isolation_verified": False,
            "companion_e2e_verified": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
