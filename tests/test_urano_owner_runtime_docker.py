"""U19 integrated gate: signed fake Google principals -> session/CSRF HTTP
-> trusted owner controller -> TWO real pinned Docker Engine workers.

No actual Google network, live app, real user media, render or Companion.
Only disposable GitHub Actions Linux with Docker may run this test.
"""
from __future__ import annotations

import os
import json
import hashlib
import hmac
import time
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
from urano.companion_receipt_auth import CompanionReceiptVerifier
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources

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
            self.controller, self.sessions, https_origin=ORIGIN, catalog=self.catalog))
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


    def test_two_real_engines_register_private_proxy_bytes_before_ingest(self):
        """C5: two real isolated Engine containers, bounded synthetic 20s MP4s.

        The test asserts the actual Engine-registered paths and Stage DONE;
        browser original claims are deliberately NOT certified.
        """
        inbox=self.root/"private-proxy-inbox"
        inbox.mkdir()
        # Operator-paired, owner-specific HMAC keys on the disposable runner.
        # This is synthetic signed identity; the actual Companion signer is
        # tested separately in test_c5_companion_proxy_receipt.py.
        keys={}
        for person in ("alice","bob"):
            secret=self.root/(person+"-pairing.key")
            secret.write_bytes(os.urandom(32))
            secret.chmod(0o600)
            keys[self.bridges[person].owner_id]=secret
        verifier=CompanionReceiptVerifier(keys)
        provenance=StageSourceProvenance(self.root/"provenance.sqlite3",self.catalog)
        self.controller.configure_trusted_attestation(
            provenance,inbox,container_workspace=Path("/workspace"))
        digests={}
        for person in ("alice","bob"):
            workspace=self.root/person
            fixture=[
                "docker","run","--rm","--network","none","--user","10001:10001",
                "--mount",f"type=bind,src={workspace},dst=/workspace",
                "--workdir","/app/engine",os.environ["URANO_TEST_IMAGE_ID"],
                "python","/app/tests/urano_u20_prepare_stage_inputs.py",
                "Owned"+person.title()
            ]
            setup=subprocess.run(fixture,capture_output=True,text=True,timeout=150)
            self.assertEqual(setup.returncode,0,setup.stderr[-1000:])
            project_id=self.project_ids[person]
            owner=self.bridges[person].owner_id
            camera=(workspace/"Projects"/("Owned"+person.title())/
                    "inputs"/"camera-a.mp4")
            self.assertTrue(camera.is_file())
            digest=hashlib.sha256(camera.read_bytes()).hexdigest()
            digests[person]=digest
            directory=inbox/hashlib.sha256(owner.encode()).hexdigest()/project_id
            directory.mkdir(parents=True,mode=0o700)
            (directory/f"slot-0-{digest}.mp4").write_bytes(camera.read_bytes())
            original={"name":person+".mp4","size":camera.stat().st_size,
                      "fingerprint":digest}
            unsigned={"schema":"montara-companion-proxy-receipt-v1",
                      "project_id":project_id,"source_slot":0,
                      "original":original,"proxy_sha256":digest}
            message=json.dumps(unsigned,sort_keys=True,separators=(",",":"),
                               ensure_ascii=True).encode()
            sig=hmac.new(keys[owner].read_bytes(),message,hashlib.sha256).hexdigest()
            authenticated=verifier.verify(owner,project_id,0,digest,original,
                                         {"receipt":unsigned,"signature":sig})
            self.assertTrue(authenticated["receipt_authenticated"])
            (directory/f"slot-0-{digest}.json").write_text(json.dumps({
                "source_slot":0,"proxy_sha256":digest,
                "original_claim":original,
                "attested":False,"bytes":camera.stat().st_size,
                "receipt_authenticated":True}))
        self.assertNotEqual(digests["alice"],"")
        self.assertEqual(self.activate("alice",self.project_ids["bob"]).status_code,404)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.activate,person,self.project_ids[person])
                     for person in ("alice","bob")]
            self.assertTrue(all(x.result(timeout=180).status_code==200 for x in futures))
        # CI fixture has host-owned files; isolated containers run UID 10001.
        # chown ONLY new synthetic staged input directories. Production requires
        # a dedicated matching OS identity, never chmod 777 on user media.
        for person in ("alice","bob"):
            bridge=self.bridges[person]
            pid=self.project_ids[person]
            from urano.trusted_stage_inputs import prepare_trusted_stage_inputs
            # The real Engine fixture generated inputs/ as UID 10001. Grant
            # the runner temporary ownership of THIS disposable directory,
            # perform trusted host-side copy, then return everything to 10001.
            # Never do this on a shared VM or on user media.
            inputs=(self.root/person/"Projects"/("Owned"+person.title())/"inputs")
            fix_parent=subprocess.run(
                ["sudo","chown",f"{os.getuid()}:{os.getgid()}",str(inputs)],
                capture_output=True,text=True,timeout=20)
            self.assertEqual(fix_parent.returncode,0,fix_parent.stderr)
            paths=prepare_trusted_stage_inputs(
                bridge.guard.bindings,inbox,bridge.owner_id,pid,source_slots={0})
            self.assertEqual(len(paths),1)
            self.assertEqual(hashlib.sha256(paths[0].read_bytes()).hexdigest(),
                             digests[person])
            scoped=paths[0].parent
            fix=subprocess.run(["sudo","chown","-R","10001:10001",str(inputs)],
                                capture_output=True,text=True,timeout=20)
            self.assertEqual(fix.returncode,0,fix.stderr)
        with ThreadPoolExecutor(max_workers=2) as pool:
            registered=[pool.submit(self.bridges[person].register_staged_inputs,
                                    self.project_ids[person])
                        for person in ("alice","bob")]
            self.assertEqual([f.result(timeout=150) for f in registered],[1,1])
        # Verify Engine persisted the exact hash-named file for each owner.
        for person in ("alice","bob"):
            workspace=self.root/person
            project_file=workspace/"Projects"/("Owned"+person.title())/"project.json"
            # Disposable CI runner only: Engine writes project.json as UID
            # 10001. Read it without changing the file's ownership/ACLs.
            saved_text=subprocess.run(
                ["sudo","cat",str(project_file)],capture_output=True,
                text=True,check=True,timeout=15).stdout
            doc=json.loads(saved_text)
            videos=doc.get("inputs",{}).get("videos") or []
            self.assertEqual(len(videos),1,doc.get("inputs",{}))
            self.assertIn(digests[person],videos[0]["path"])
            self.assertNotIn("Owned"+("Bob" if person=="alice" else "Alice"),
                             videos[0]["path"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            started=[pool.submit(self._stage_post,person,self.project_ids[person])
                     for person in ("alice","bob")]
            self.assertEqual([f.result(timeout=100).status_code for f in started],
                             [202,202])
        deadline=time.monotonic()+240
        done=set()
        while len(done)<2 and time.monotonic()<deadline:
            for person in ("alice","bob"):
                if person in done: continue
                client,_=self.clients[person]
                response=client.get(
                    f"/urano/v1/runtime/projects/{self.project_ids[person]}/ingest",
                    base_url=ORIGIN)
                self.assertEqual(response.status_code,200,response.get_data(as_text=True))
                status=response.json["status"]
                self.assertNotIn(status,("blocked","failed"))
                if status=="done":done.add(person)
            time.sleep(.5)
        self.assertEqual(done,{"alice","bob"})
        # A real Engine DONE now drives the operator-only final certificate.
        # None of this flow can be triggered by an arbitrary browser claim.
        for person in ("alice","bob"):
            bridge=self.bridges[person]
            try:
                verified=provenance.verified(
                    bridge.owner_id,self.project_ids[person],source_slots={0})
            except UnverifiedSources as missing:
                from urano.stage_ingest_attestation import attest_authenticated_inbox
                bound=bridge.guard.bindings.resolve_internal(
                    bridge.owner_id,self.project_ids[person])
                try:
                    attest_authenticated_inbox(
                        provenance,bridge.guard.bindings,inbox,
                        bridge.owner_id,self.project_ids[person],
                        engine_project_file=bound/"project.json",
                        container_workspace=Path("/workspace"))
                except Exception as reason:
                    # Internal CI diagnostic only; never return paths to HTTP.
                    self.fail("Automatic Stage provenance unavailable: "+
                              type(reason).__name__+" "+str(reason))
                self.fail("Controller did not attest despite direct verifier success")
            self.assertEqual(verified["sources"][0]["original"]["name"],
                             person+".mp4")
            self.assertRegex(verified["stage_revision"],r"^[a-f0-9]{64}$")
        with self.assertRaises(Exception):
            provenance.verified(
                self.bridges["alice"].owner_id,self.project_ids["bob"],
                source_slots={0})
        self.assertEqual(self.close("alice").status_code,200)
        self.assertEqual(self.close("bob").status_code,200)

    def _stage_post(self, who, project_id):
        client, session = self.clients[who]
        return client.post(f"/urano/v1/runtime/projects/{project_id}/ingest",
                           base_url=ORIGIN, headers={
                               "Origin":ORIGIN, "X-Urano-CSRF":session.csrf})

    def test_real_stage_ingest_from_owner_session_and_safe_handoff(self):
        # Trusted CI-only fixture provisioning, never a browser upload/path.
        for person in ("alice", "bob"):
            owner_workspace = self.root / person
            cmd = ["docker","run","--rm","--network","none",
                   "--user","10001:10001","--mount",
                   f"type=bind,src={owner_workspace},dst=/workspace",
                   "--workdir","/app/engine",os.environ["URANO_TEST_IMAGE_ID"],
                   "python","/app/tests/urano_u20_prepare_stage_inputs.py",
                   "Owned"+person.title()]
            provision = subprocess.run(cmd,capture_output=True,text=True,timeout=130)
            self.assertEqual(provision.returncode,0,provision.stderr[-1400:])
            self.assertIn('"fixture_prepared": true',provision.stdout)

        # Unowned Stage requests are denied before any worker starts.
        alien = self._stage_post("alice",self.project_ids["bob"])
        self.assertEqual(alien.status_code,404)
        self.assertIsNone(self.bridges["alice"].process)

        with ThreadPoolExecutor(max_workers=2) as pool:
            opened = [pool.submit(self.activate, person,self.project_ids[person])
                      for person in ("alice","bob")]
            self.assertTrue(all(f.result(timeout=180).status_code==200 for f in opened))
            started = [pool.submit(self._stage_post,person,self.project_ids[person])
                       for person in ("alice","bob")]
            submissions = [f.result(timeout=100) for f in started]
        diagnostics = {}
        for person in ("alice", "bob"):
            project_file = (self.root / person / "Projects" /
                            ("Owned" + person.title()) / "project.json")
            # CI synthetic media belongs to Docker UID 10001; inspect only
            # with sudo on this disposable runner, never on user machines.
            saved_text = subprocess.run(["sudo","cat",str(project_file)],
                                        capture_output=True,text=True,check=True,timeout=10).stdout
            saved = json.loads(saved_text)
            diagnostics[person] = {
                "video_records": len(saved.get("inputs", {}).get("videos") or []),
                "master_record": bool(saved.get("inputs", {}).get("master")),
                "stage_state": saved.get("stages", {}).get("ingest", {}).get("status"),
                "engine_http_reject": self.bridges[person].last_ingest_failure_code,
            }
        self.assertEqual([r.status_code for r in submissions],[202,202],diagnostics)
        self.assertEqual([r.json["stage"] for r in submissions],["ingest","ingest"])
        deadline = time.monotonic()+210
        done = set()
        last = {}
        while len(done)!=2 and time.monotonic()<deadline:
            for person in ("alice","bob"):
                if person in done: continue
                client,_=self.clients[person]
                response=client.get(
                    f"/urano/v1/runtime/projects/{self.project_ids[person]}/ingest",
                    base_url=ORIGIN)
                self.assertEqual(response.status_code,200,response.get_data(as_text=True))
                status=response.json["status"]
                last[person]=status
                self.assertNotIn(status,("failed","blocked"))
                if status=="done":done.add(person)
            time.sleep(.35)
        self.assertEqual(done,{"alice","bob"},last)
        for person in ("alice","bob"):
            bridge=self.bridges[person]
            self.assertEqual(bridge.guard.get_state(
                bridge.owner_id,bridge.runtime_id)[0],"ready")

            # No paths or source files are handed to Companion. Edits are
            # deliberately not render-ready without local original matching.
            saved=self.catalog.get(bridge.owner_id,self.project_ids[person])
            self.catalog.save_recipe(
                bridge.owner_id,self.project_ids[person],
                {"urano_edits_v1":{"cuts":[
                    {"source_slot":0,"start_ms":500,"end_ms":1200}]}},
                expected_revision=saved.revision)
            client,_=self.clients[person]
            response=client.get(
                f"/urano/v1/runtime/projects/{self.project_ids[person]}/companion-handoff",
                base_url=ORIGIN)
            self.assertEqual(response.status_code,200,response.get_data(as_text=True))
            plan=response.json["plan"]
            self.assertFalse(plan["render_ready"])
            self.assertFalse(plan["local_source_resolution_verified"])
            self.assertEqual(plan["cuts"][0]["end_ms"],1200)
            self.assertNotIn("/workspace",response.get_data(as_text=True))
            self.assertNotIn("source_files",response.get_data(as_text=True))
            # Optional U22 single-runner handoff: emit ONLY the owner-authorized
            # JSON descriptor after the real Engine Ingest reached DONE.
            # Never emit input videos, project file, cookie, source path or JWT.
            archive = os.environ.get("URANO_U22_HANDOFF_DIR")
            if archive:
                destination = Path(archive)
                if not destination.is_dir() or destination.is_symlink():
                    raise AssertionError("U22 scratch directory must exist")
                (destination / (person+".json")).open("x",encoding="utf-8").write(
                    json.dumps({"owner": person, "plan": plan})+"\n")
        client,_=self.clients["alice"]
        self.assertEqual(client.get(
            f"/urano/v1/runtime/projects/{self.project_ids['bob']}/companion-handoff",
            base_url=ORIGIN).status_code,404)
        self.assertEqual(self.close("alice").status_code,200)
        self.assertEqual(self.close("bob").status_code,200)


if __name__ == "__main__":
    unittest.main()
