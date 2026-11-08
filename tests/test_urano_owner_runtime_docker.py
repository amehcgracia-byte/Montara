"""U19 integrated gate: signed fake Google principals -> session/CSRF HTTP
-> trusted owner controller -> TWO real pinned Docker Engine workers.

No actual Google network, live app, real user media, render or Companion.
Only disposable GitHub Actions Linux with Docker may run this test.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask

from test_google_flow_contract import SignedFakeGoogle, CLIENT
import test_google_private_engine_docker as engine_fixture

from urano.container_worker_bridge import ContainerWorkerBridge
from urano.engine_bindings import EngineProjectRegistry
from urano.google_oidc import verify_google_id_token
from urano.google_owner import GoogleOwnerStore
from urano.http_owner_runtime import owner_runtime_blueprint
from urano.owner_runtime_controller import OwnerRuntimeController
from urano.project_catalog import ProjectCatalog
from urano.runtime_activation import RuntimeActivationGuard
from urano.session_auth import SESSION_COOKIE, SessionStore

ORIGIN = "https://lab.example.test"


@unittest.skipUnless(os.name == "posix" and
                     os.environ.get("GITHUB_ACTIONS") == "true" and
                     os.environ.get("URANO_TEST_IMAGE_ID"),
                     "Real Docker only on disposable GitHub Actions")
class OwnerSessionToRealEngine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="urano-u19-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.cleanup_ci)
        self.catalog = ProjectCatalog(self.root / "projects.sqlite3")
        self.sessions = SessionStore(self.root / "sessions.sqlite3")
        owners = GoogleOwnerStore(self.root / "owners.sqlite3")
        signed = SignedFakeGoogle()
        self.controller = OwnerRuntimeController()
        self.clients, self.project_ids, self.bridges = {}, {}, {}
        allowed = frozenset({"alice@example.test", "bob@example.test"})
        app = Flask("u19-real-engine")
        app.register_blueprint(owner_runtime_blueprint(
            self.controller, self.sessions, https_origin=ORIGIN))
        self.app = app
        for person in ("alice", "bob"):
            signed.sub, signed.email = "fake-google-sub-" + person, person + "@example.test"
            identity = verify_google_id_token(
                signed.token("u19-two-owners-nonce-long-enough"), client_id=CLIENT,
                expected_nonce="u19-two-owners-nonce-long-enough", jwks=signed.jwks())
            owner = owners.resolve_beta_owner(identity, allowed_emails=allowed)
            workspace = self.root / person
            workspace.mkdir(mode=0o777)
            workspace.chmod(0o777)
            (workspace / "Projects").mkdir(mode=0o777)
            (workspace / "Projects").chmod(0o777)
            project_folder = "Owned" + person.title()
            engine_fixture._make_project(os.environ["URANO_TEST_IMAGE_ID"], workspace, project_folder)
            project = self.catalog.create(owner, project_folder)
            self.project_ids[person] = project.id
            binding = EngineProjectRegistry(
                self.root / (person + "-binding.sqlite3"), workspace, self.catalog)
            binding.bind_trusted(owner, project.id, project_folder)
            guard = RuntimeActivationGuard(
                self.root / (person + "-runtime.sqlite3"), self.catalog, binding)
            runtime = guard.register_trusted(owner)
            bridge = ContainerWorkerBridge(
                guard=guard, owner_id=owner, runtime_id=runtime,
                workspace=workspace, image=os.environ["URANO_TEST_IMAGE_ID"],
                name="urano-u19-" + person + "-private",
                worker_command=engine_fixture.ENGINE_COMMAND, startup_timeout=115,
                open_timeout=100, memory_mb=1536, cpus=1.0)
            self.controller.register_trusted(owner, bridge)
            self.bridges[person] = bridge
            client = self.app.test_client()
            session = self.sessions.issue(owner)
            client.set_cookie(SESSION_COOKIE, session.token, domain="lab.example.test", secure=True)
            self.clients[person] = (client, session)

    def cleanup_ci(self):
        try:
            for bridge in getattr(self, "bridges", {}).values():
                try:
                    bridge.stop()
                except Exception:
                    pass
        finally:
            # Scratch-only: files belong to the container UID 10001. Not a
            # permitted cleanup pattern on any customer/shared machine.
            reclaim = subprocess.run(
                ["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(self.root)],
                capture_output=True, timeout=25)
            if reclaim.returncode != 0:
                raise AssertionError("Docker fixture cleanup failed")
            self.temp.cleanup()

    def activate(self, who, project_id):
        client, session = self.clients[who]
        return client.post(f"/urano/v1/runtime/projects/{project_id}/activate",
                           base_url=ORIGIN,
                           headers={"Origin":ORIGIN, "X-Urano-CSRF": session.csrf})

    def close(self, who):
        client, session = self.clients[who]
        return client.post("/urano/v1/runtime/close", base_url=ORIGIN,
                           headers={"Origin": ORIGIN, "X-Urano-CSRF": session.csrf})

    def test_signed_owner_session_controls_two_independent_real_engines(self):
        # The foreign attempt must fail BEFORE starting any Docker worker.
        self.assertEqual(self.activate("alice",self.project_ids["bob"]).status_code,404)
        self.assertIsNone(self.bridges["alice"].process)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self.activate, "alice", self.project_ids["alice"])
            b = pool.submit(self.activate, "bob", self.project_ids["bob"])
            ra, rb = a.result(timeout=180), b.result(timeout=180)
        self.assertEqual((ra.status_code,rb.status_code),(200,200),
                         (ra.get_data(as_text=True),rb.get_data(as_text=True)))
        self.assertNotEqual(self.bridges["alice"].cid,self.bridges["bob"].cid)
        for who,other in (("alice","bob"),("bob","alice")):
            bridge = self.bridges[who]
            self.assertEqual(bridge.guard.get_state(
                bridge.owner_id,bridge.runtime_id)[0],"ready")
            # No other-owner synthetic Engine folders mounted inside container.
            inside = subprocess.run(
                ["docker","exec",bridge.cid,"test","-e",
                 "/workspace/Projects/Owned"+other.title()],
                capture_output=True,timeout=20)
            self.assertNotEqual(inside.returncode,0)
        # Owner A shutting down cannot affect owner B.
        self.assertEqual(self.close("alice").status_code,200)
        self.assertEqual(self.bridges["bob"].guard.get_state(
            self.bridges["bob"].owner_id,self.bridges["bob"].runtime_id)[0],"ready")
        self.assertEqual(self.close("bob").status_code,200)
        for bridge in self.bridges.values():
            self.assertIsNone(bridge.cid)


if __name__ == "__main__":
    unittest.main()
