"""U19: authenticated owner-only Engine activation, with real U13 guard/registry.

Offline fake Docker transport here: the Docker real Engine control-path gate
is separate and must use a pinned actual image on a disposable runner.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.container_worker_bridge import ContainerWorkerBridge
from urano.engine_bindings import EngineProjectRegistry
from urano.http_owner_runtime import owner_runtime_blueprint
from urano.owner_runtime_controller import OwnerRuntimeController
from urano.project_catalog import ProjectCatalog
from urano.runtime_activation import RuntimeActivationGuard
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://lab.example.test"


class RunningFake:
    def poll(self):
        return None


class EmulatedPrivateContainer(ContainerWorkerBridge):
    """Transport fake, NOT a substitute for the real Docker acceptance."""
    def __init__(self, *, owner_id, guard, runtime_id):
        self.owner_id, self.guard, self.runtime_id = owner_id, guard, runtime_id
        self.process = None
        self.starts = 0
        self.opens = 0
        self.stops = 0
        self.generation = None

    def start(self):
        self.starts += 1
        self.process = RunningFake()

    def open_project(self, project_id):
        ticket = self.guard.request_open(self.owner_id, self.runtime_id, project_id)
        self.guard.acknowledge_open(self.owner_id, ticket, success=True)
        self.generation = ticket.generation
        self.opens += 1
        return ticket

    def stop(self):
        self.stops += 1
        self.process = None
        if self.generation is not None:
            self.guard.invalidate_after_worker_exit(
                self.owner_id, self.runtime_id, self.generation)
            self.generation = None


class OwnerPrivateRuntimeContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="urano-u19-unit-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.catalog = ProjectCatalog(root / "catalog.sqlite3")
        self.controller = OwnerRuntimeController()
        self.projects = {}
        self.bridges = {}
        for nickname in ("alice", "bob"):
            owner = "owner-" + nickname
            workspace = root / ("ws-" + nickname)
            project_dir = workspace / "Projects" / ("Stage-" + nickname)
            project_dir.mkdir(parents=True)
            (project_dir / "project.json").write_text('{"stage":"synthetic"}')
            catalog_project = self.catalog.create(owner, nickname + " Stage")
            bindings = EngineProjectRegistry(root / (nickname + "-bindings.sqlite3"),
                                             workspace, self.catalog)
            bindings.bind_trusted(owner, catalog_project.id, project_dir.name)
            guard = RuntimeActivationGuard(root / (nickname + "-runtime.sqlite3"),
                                           self.catalog, bindings)
            runtime_id = guard.register_trusted(owner)
            bridge = EmulatedPrivateContainer(owner_id=owner, guard=guard,
                                              runtime_id=runtime_id)
            self.controller.register_trusted(owner, bridge)
            self.projects[nickname] = catalog_project.id
            self.bridges[nickname] = bridge
        app = Flask("u19-private-runtime")
        app.register_blueprint(owner_runtime_blueprint(
            self.controller, self.sessions, https_origin=ORIGIN))
        self.clients = {}
        for nickname in ("alice", "bob"):
            client = app.test_client()
            session = self.sessions.issue("owner-" + nickname)
            client.set_cookie(SESSION_COOKIE, session.token, domain="lab.example.test", secure=True)
            self.clients[nickname] = (client, session)
        self.anon = app.test_client()

    def activate(self, nickname, project_id, *, csrf=None, origin=ORIGIN,
                 json_payload=None):
        client, session = self.clients[nickname]
        headers = {"Origin": origin, "X-Urano-CSRF": csrf if csrf is not None else session.csrf}
        return client.post(f"/urano/v1/runtime/projects/{project_id}/activate",
                           headers=headers, base_url=ORIGIN, json=json_payload)

    def close(self, nickname):
        client, session = self.clients[nickname]
        return client.post("/urano/v1/runtime/close", base_url=ORIGIN,
                           headers={"Origin": ORIGIN, "X-Urano-CSRF": session.csrf})

    def test_two_owners_activate_independent_engine_states(self):
        a = self.activate("alice", self.projects["alice"])
        b = self.activate("bob", self.projects["bob"])
        self.assertEqual(a.status_code, 200)
        self.assertEqual(b.status_code, 200)
        self.assertEqual(a.json, {"state":"ready","render_access":False,
                                   "companion_access":False})
        self.assertEqual(self.bridges["alice"].starts, 1)
        self.assertEqual(self.bridges["bob"].starts, 1)
        self.assertEqual(self.bridges["alice"].opens, 1)
        self.assertEqual(self.bridges["bob"].opens, 1)
        self.assertEqual(self.close("alice").json["state"], "idle")
        self.assertEqual(self.bridges["bob"].guard.get_state(
            "owner-bob", self.bridges["bob"].runtime_id)[0], "ready")
        self.assertEqual(self.close("bob").json["state"], "idle")

    def test_foreign_project_denied_before_worker_start(self):
        out = self.activate("alice", self.projects["bob"])
        self.assertEqual(out.status_code, 404)
        self.assertEqual(self.bridges["alice"].starts, 0)
        self.assertEqual(self.bridges["bob"].starts, 0)
        self.assertNotIn(str(self.projects["bob"]), out.get_data(as_text=True))

    def test_no_cookie_csrf_or_wrong_origin_cannot_start(self):
        path = f"/urano/v1/runtime/projects/{self.projects['alice']}/activate"
        self.assertEqual(self.anon.post(path, base_url=ORIGIN).status_code, 401)
        self.assertEqual(self.activate("alice",self.projects["alice"],csrf="invalid").status_code,403)
        self.assertEqual(self.activate("alice",self.projects["alice"],origin="https://evil.example.test").status_code,403)
        self.assertEqual(self.activate("alice",self.projects["alice"],json_payload={"owner_id":"owner-bob"}).status_code,400)
        self.assertEqual(self.bridges["alice"].starts, 0)
        self.assertEqual(self.bridges["bob"].starts, 0)

    def test_forged_owner_headers_ignored_and_logout_revokes(self):
        client, session = self.clients["alice"]
        path = f"/urano/v1/runtime/projects/{self.projects['bob']}/activate"
        out = client.post(path, headers={"Origin": ORIGIN,
                          "X-Urano-CSRF":session.csrf,
                          "X-Owner-ID":"owner-bob"},
                          query_string={"owner_id":"owner-bob",
                                        "folder":"Stage-bob"}, base_url=ORIGIN)
        self.assertEqual(out.status_code,404)
        self.sessions.revoke(session.token)
        self.assertEqual(self.activate("alice",self.projects["alice"]).status_code,401)

    def test_status_no_paths_and_no_activation_by_get(self):
        client, _ = self.clients["alice"]
        out = client.get("/urano/v1/runtime/state", base_url=ORIGIN)
        self.assertEqual((out.status_code,out.json["state"]),(200,"idle"))
        self.assertFalse(out.json["render_access"])
        self.assertEqual(out.headers["Cache-Control"], "no-store")
        self.assertEqual(self.bridges["alice"].starts,0)
        self.assertEqual(client.get("/urano/v1/runtime/close",base_url=ORIGIN).status_code,405)

    def test_duplicate_registration_or_cross_owner_worker_fails(self):
        with self.assertRaises(ValueError):
            self.controller.register_trusted("owner-alice", self.bridges["bob"])
        with self.assertRaises(ValueError):
            self.controller.register_trusted("owner-alice", self.bridges["alice"])


if __name__ == "__main__":
    unittest.main()
