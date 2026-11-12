"""I39 operator-only lab: COMPLETE original JM Flask editor, Owner UUID and U13A.

Needs a temporary checkout of a reviewed JM branch with its original app.py,
web/ and all product modules, plus a pinned real Engine Python site directory.
DO NOT execute in a shared tenant process, live beta, or on owner's media.
This is a single isolated synthetic project, NOT a multiuser security test.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("This physical lab requires --execute")
    bundle = args.bundle.resolve(strict=True)
    if (bundle.parent != Path("/opt/montara/bundles")
            or not bundle.name.startswith("engine-")
            or len(bundle.name) != 47
            or any(c not in "0123456789abcdef" for c in bundle.name[7:])):
        parser.error("Use the reviewed, pinned real Engine bundle")
    source = Path(__file__).resolve().parents[1]
    if (not (source / "app.py").is_file()
            or not (source / "web/index.html").is_file()
            or not (source / "engine/server/api.py").is_file()):
        parser.error("Requires a complete JM editor checkout with Engine")
    # Keep the product source ahead of the pinned dependencies. Never load a
    # second or alternative Engine from a globally installed Python package.
    sys.path[:0] = [str(source), str(bundle / "site"),
                    str(bundle / "app"), str(bundle / "engine")]
    from app import create_montara_app
    from core.project import new_project_document
    from urano.project_catalog import ProjectCatalog
    from urano.engine_bindings import EngineProjectRegistry
    from urano.owner_jm_editor_handoff import bind_open_jm_editor_project, EditorHandoffDenied

    with tempfile.TemporaryDirectory(prefix="montara-i39-owner-jm-") as temp:
        root = Path(temp)
        catalog = ProjectCatalog(root / "owner-projects.sqlite3")
        a = catalog.create("owner-lab-a", "JM Stage", recipe={
            "montara_beta_workspace": {"version": 1, "mode": "stage"}
        })
        b = catalog.create("owner-lab-b", "Other", recipe={
            "montara_beta_workspace": {"version": 1, "mode": "stage"}
        })
        data_root = root / "private-jm"
        folder = data_root / "Projects" / a.id
        folder.mkdir(parents=True)
        (folder / "project.json").write_text(
            json.dumps(new_project_document(a.id)), encoding="utf-8")
        registry = EngineProjectRegistry(root / "binding.sqlite3", data_root, catalog)
        app = create_montara_app(data_root, samples=False)
        with app.test_client() as browser:
            html = browser.get("/")
            version = browser.get("/montara/version")
            initial = browser.get("/api/v1/wizard/status")
            open_response = browser.post(
                "/api/v1/wizard/projects/open", json={"path": str(folder)}
            )
            project_data = browser.get("/api/v1/project")
            if (html.status_code != 200 or version.status_code != 200
                    or initial.status_code != 200
                    or open_response.status_code != 200
                    or project_data.status_code != 200):
                raise RuntimeError("Complete original JM app did not open Owner project")
            if (b'data-platform="youtube"' not in html.data
                    or b'data-platform="reel"' not in html.data
                    or b'data-platform="show"' not in html.data):
                raise RuntimeError("Original Stage/Push/Show editor not served")
        binding = bind_open_jm_editor_project(
            owner_id="owner-lab-a", project_id=a.id, mode="stage",
            catalog=catalog, registry=registry, engine_client=app.test_client(),
        )
        # Flask.test_client() does not expose .application on all Flask
        # versions, use the real application state with its own GET adapter.
        if binding.catalog_project_id != a.id:
            raise RuntimeError("JM project binding differed from Owner UUID")
        try:
            bind_open_jm_editor_project(
                owner_id="owner-lab-b", project_id=b.id, mode="stage",
                catalog=catalog, registry=registry, engine_client=app.test_client(),
            )
        except EditorHandoffDenied:
            pass
        else:
            raise RuntimeError("Foreign owner claimed an active JM project")
        print(json.dumps({
            "complete_original_jm_html": True,
            "jm_editor_stage_push_show": True,
            "real_pinned_engine": True,
            "real_owner_uuid_opened": True,
            "existing_u13a_binding": True,
            "foreign_owner_rejected": True,
            "registered_browser_media": False,
            "private_systemd_uid_proven": False,
            "companion_windows_export_proven": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
