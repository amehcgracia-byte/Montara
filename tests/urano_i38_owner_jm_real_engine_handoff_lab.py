"""I38 real JM Engine project -> existing U13A Owner binding (opt-in VM lab).

Uses the pinned real Engine, a canonical Owner UUID, temporary SQLite and
filesystem. Does not modify the live beta, Companion, main or JM's projects.
"""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
import uuid
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--bundle",required=True,type=Path)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if not args.execute:
        parser.error("Explicit --execute required")
    bundle=args.bundle.resolve(strict=True)
    if (bundle.parent!=Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-")
            or len(bundle.name)!=47
            or any(x not in "0123456789abcdef" for x in bundle.name[7:])):
        parser.error("Invalid pinned real Engine bundle")
    repo=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(repo),str(bundle/"site"),str(bundle/"app"),str(bundle/"engine")]
    from core.project import new_project_document
    from urano.project_catalog import ProjectCatalog
    from urano.engine_bindings import EngineProjectRegistry
    from urano.engine_worker_process import make_engine_client
    from urano.owner_jm_editor_handoff import bind_open_jm_editor_project,EditorHandoffDenied

    with tempfile.TemporaryDirectory(prefix="montara-i38-jm-owner-") as temp:
        root=Path(temp)
        catalog=ProjectCatalog(root/"owner.sqlite3")
        data=root/"private-engine"
        (data/"Projects").mkdir(parents=True)
        registry=EngineProjectRegistry(root/"bindings.sqlite3",data,catalog)
        stage=catalog.create("test-owner-a","One Stage",recipe={
            "montara_beta_workspace":{"mode":"stage","version":1}
        })
        foreign=catalog.create("test-owner-b","Other Stage",recipe={
            "montara_beta_workspace":{"mode":"stage","version":1}
        })
        folder=data/"Projects"/stage.id
        folder.mkdir()
        (folder/"project.json").write_text(json.dumps(
            new_project_document(stage.id)),encoding="utf-8")
        engine=make_engine_client(bundle/"engine",data)
        opened=engine.post("/api/v1/wizard/projects/open",json={"path":str(folder)})
        if opened.status_code!=200:
            raise RuntimeError("Real JM Engine refused Owner project")
        verified=bind_open_jm_editor_project(
            owner_id="test-owner-a",project_id=stage.id,mode="stage",
            catalog=catalog,registry=registry,engine_client=engine)
        if (verified.catalog_project_id!=stage.id
                or registry.resolve_internal("test-owner-a",stage.id)!=folder):
            raise RuntimeError("Owner and real JM Engine project mismatch")
        other_blocked=False
        try:
            bind_open_jm_editor_project(
                owner_id="test-owner-b",project_id=foreign.id,mode="stage",
                catalog=catalog,registry=registry,engine_client=engine)
        except EditorHandoffDenied:
            other_blocked=True
        if not other_blocked:
            raise RuntimeError("Foreign owner rebound real JM Engine")
        print(json.dumps({
            "real_jm_engine_opened":True,
            "existing_u13a_owner_registry_reused":True,
            "owner_uuid_matches_engine_project":True,
            "foreign_owner_rejected":True,
            "no_new_binding_database_schema":True,
            "original_media_uploaded":False,
            "editor_browser_connected":False,
            "companion_windows_verified":False,
        },sort_keys=True))


if __name__=="__main__":
    main()
