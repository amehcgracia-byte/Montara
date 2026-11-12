"""I37 opt-in lab: HTTPS Flask Owner -> broker Unix -> Engine Unix -> REAL Stage.

No deployed service or root privilege. A minted *local synthetic session* tests
the same SessionStore/CSRF path as Google login, but NOT Google's OAuth itself.
The broker and worker run under the same lab UID: this proves transport, NOT
the required separate production DynamicUser/cgroup identity.

Run with the pinned Linux Engine bundle Python and --execute. No media.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from unittest.mock import patch


ORIGIN = "https://montara-owner-lab.invalid"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Use --execute only on an isolated Linux lab")
    bundle = args.bundle.resolve(strict=True)
    if (bundle.parent != Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-")
            or len(bundle.name) != 47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Invalid pinned Engine bundle")
    repo_root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(repo_root), str(bundle / "site"),
                    str(bundle / "app"), str(bundle / "engine")]
    from flask import Flask
    from core.project import new_project_document
    from urano.project_catalog import ProjectCatalog
    from urano.session_auth import SessionStore, SESSION_COOKIE
    from urano.job_recovery_ledger import JobRecoveryLedger
    from urano.owner_broker_preview import owner_engine_preview_blueprint
    from urano.engine_worker_process import make_engine_client
    from urano.private_stage_unix_transport import (
        serve_stage_socket, SystemdUnixStageTransport,
    )
    from urano.private_stage_payload import private_stage_snapshot
    from urano.private_stage_snapshot_bridge import trusted_stage_snapshot
    from urano.private_stage_owner_admission import ReadOnlyOwnerCatalog
    from urano.private_broker_service import dispatch_owner
    from urano.restricted_systemd_broker import expected_cgroup

    with tempfile.TemporaryDirectory(prefix="montara-i37-real-e2e-") as temp:
        root = Path(temp)
        data = root / "owner"
        data.mkdir(mode=0o700)
        catalog = ProjectCatalog(data / "projects.sqlite3")
        sessions = SessionStore(data / "sessions.sqlite3")
        mine = catalog.create(
            "owner-lab-a", "Lab Stage",
            recipe={"montara_beta_workspace": {"mode": "stage"}},
        )
        foreign = catalog.create(
            "owner-lab-b", "Other owner",
            recipe={"montara_beta_workspace": {"mode": "stage"}},
        )
        auth = sessions.issue("owner-lab-a")
        ledger = JobRecoveryLedger(root / "ledger.sqlite3")
        lease = ledger.start_trusted("owner-lab-a", mine.id)
        unit = ledger.reserve_target_unit(lease)
        lease = ledger.mark_running(lease)

        worker_root = root / unit
        folder = worker_root / "Projects" / mine.id
        folder.mkdir(parents=True)
        (folder / "project.json").write_text(
            json.dumps(new_project_document(mine.id)), encoding="utf-8")
        client = make_engine_client(bundle / "engine", worker_root)
        opened = client.post("/api/v1/wizard/projects/open",
                             json={"path": str(folder)})
        if opened.status_code != 200:
            raise RuntimeError("Real Engine refused project")

        errors = []
        ready = threading.Event()

        def worker():
            try:
                serve_stage_socket(
                    worker_root, project_id=mine.id,
                    generation=lease.generation,
                    trusted_broker_uid=os.getuid(),
                    read_snapshot=lambda: private_stage_snapshot(client, folder),
                    on_listening=ready.set, max_requests=1,
                )
            except Exception as exc:
                errors.append("worker:" + type(exc).__name__)

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()
        if not ready.wait(timeout=8):
            raise RuntimeError("Stage worker listener not ready")

        systemd = SystemdUnixStageTransport(
            lambda target: {
                "ActiveState": "active",
                "ControlGroup": expected_cgroup(target),
                "MainPID": str(os.getpid()),
            }, runtime_root=root,
        )

        class Broker:
            def stage_snapshot_owner(self, owner_id, project_id,
                                     generation, owner_db_root):
                snapshot = trusted_stage_snapshot(
                    owner_id, project_id, generation=generation,
                    catalog=ReadOnlyOwnerCatalog(owner_db_root),
                    ledger=ledger,
                    engine_sha=bundle.name[7:],
                    transport=systemd,
                )
                return {"ok": True, **snapshot}

        broker_socket = root / "broker.sock"
        broker_ready = threading.Event()
        def broker_loop():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(str(broker_socket))
                    server.listen(1)
                    broker_ready.set()
                    conn, _ = server.accept()
                    with conn:
                        result = dispatch_owner(conn, os.getuid(), data, Broker())
                        conn.sendall(json.dumps(result).encode() + b"\n")
            except Exception as exc:
                errors.append("broker:" + type(exc).__name__)

        broker_thread = threading.Thread(target=broker_loop, daemon=True)
        broker_thread.start()
        if not broker_ready.wait(timeout=8):
            raise RuntimeError("Stage broker listener not ready")
        app = Flask("i37-real-stage")
        app.register_blueprint(owner_engine_preview_blueprint(
            catalog, sessions, https_origin=ORIGIN))
        http = app.test_client()
        http.set_cookie(SESSION_COOKIE, auth.token,
                        domain="montara-owner-lab.invalid")
        headers = {"X-Urano-CSRF": auth.csrf}
        with patch("urano.owner_broker_preview.SOCKET", str(broker_socket)):
            other = http.get(
                f"/urano/v1/projects/{foreign.id}/stage-status?generation={lease.generation}",
                base_url=ORIGIN, headers=headers)
            if other.status_code != 404:
                raise RuntimeError("Foreign project was not denied")
            result = http.get(
                f"/urano/v1/projects/{mine.id}/stage-status?generation={lease.generation}",
                base_url=ORIGIN, headers=headers)
        broker_thread.join(timeout=8)
        worker_thread.join(timeout=8)
        if result.status_code != 200 or errors or broker_thread.is_alive() or worker_thread.is_alive():
            raise RuntimeError(f"Real Stage request failed: http={result.status_code} errors={errors}")
        state = result.get_json()
        if (state.get("camera_count") != 0
                or set(state.get("stages", {})) != {"ingest", "sync", "cut", "edit", "export"}
                or any("path" in key for key in state)):
            raise RuntimeError("Engine status or redaction mismatch")
        print(json.dumps({
            "real_engine_open": True,
            "private_owner_session_verified": True,
            "foreign_project_http_denied": True,
            "broker_unix_socket_verified": True,
            "worker_unix_socket_verified": True,
            "stage_http_status": result.status_code,
            "stages": state["stages"],
            "physical_multiuser_isolation_verified": False,
            "google_oauth_verified_in_this_lab": False,
            "companion_video_export_verified": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
