"""Integration of actual signed fake Google Code+PKCE login with owner-private
Engine activation through the SAME catalog/session DB. No direct session
issuance or forged owner header. Docker is emulated here; real Docker in CI.
"""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from test_google_flow_contract import SignedFakeGoogle, HOST, CLIENT, CALLBACK
from test_urano_owner_runtime_http import EmulatedPrivateContainer
from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from urano.google_owner import GoogleOwnerStore
from urano.project_catalog import ProjectCatalog
from urano.engine_bindings import EngineProjectRegistry
from urano.runtime_activation import RuntimeActivationGuard
from urano.owner_runtime_controller import OwnerRuntimeController

class FullOwnerToEngineIntegration(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="montara-c2-")
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.google=SignedFakeGoogle()
        self.controller=OwnerRuntimeController()
        self.app=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                    frozenset({"alpha@example.test","beta@example.test"})),
            provider=self.google,runtime_controller=self.controller)
        self.catalog=ProjectCatalog(self.root/"projects.sqlite3")
        self.owners=GoogleOwnerStore(self.root/"owners.sqlite3")
        self.a=self.app.test_client()
        self.b=self.app.test_client()

    def login(self,client,*,sub,email):
        self.google.sub,self.google.email=sub,email
        start=client.get("/urano/v1/google/start",base_url=HOST)
        self.assertEqual(start.status_code,302)
        params={key:values[0] for key,values in parse_qs(
            urlsplit(start.headers["Location"]).query).items()}
        self.google.nonce=params["nonce"]
        self.google.expected_challenge=params["code_challenge"]
        self.google.code="fake-provider-code"
        response=client.get("/urano/v1/google/callback",base_url=HOST,
            query_string={"state":params["state"],"code":self.google.code})
        self.assertEqual(response.status_code,303,response.get_data(as_text=True))
        refresh=client.post("/urano/v1/session/refresh",base_url=HOST,
            headers={"Origin":HOST})
        self.assertEqual(refresh.status_code,200)
        with self.owners._connect() as db:
            owner=db.execute("SELECT owner_id FROM urano_google_owners WHERE google_sub=?",
                             (sub,)).fetchone()[0]
        return owner,refresh.json["csrf"]

    def provision(self,owner,who):
        # Trusted infrastructure ONLY. No HTTP endpoint accepts this folder
        # path, owner, runtime id, container image, or Docker command.
        project=self.catalog.create(owner,who+" private")
        folder=self.root/("workspace-"+who)/"Projects"/("Stage-"+who)
        folder.mkdir(parents=True)
        (folder/"project.json").write_text('{"synthetic":true}')
        bindings=EngineProjectRegistry(self.root/(who+"-binding.sqlite3"),
              folder.parent.parent,self.catalog)
        bindings.bind_trusted(owner,project.id,folder.name)
        guard=RuntimeActivationGuard(self.root/(who+"-runtime.sqlite3"),
             self.catalog,bindings)
        runtime=guard.register_trusted(owner)
        bridge=EmulatedPrivateContainer(owner_id=owner,guard=guard,runtime_id=runtime)
        self.controller.register_trusted(owner,bridge)
        return project.id,bridge

    def post(self,client,project_id,csrf,headers=None):
        return client.post("/urano/v1/runtime/projects/"+project_id+"/activate",
            base_url=HOST,headers={"Origin":HOST,"X-Urano-CSRF":csrf,**(headers or {})})

    def test_signed_login_to_same_owner_private_worker_end_to_end(self):
        a,ac=self.login(self.a,sub="google-sub-a",email="alpha@example.test")
        b,bc=self.login(self.b,sub="google-sub-b",email="beta@example.test")
        self.assertNotEqual(a,b)
        ap,aw=self.provision(a,"alice")
        bp,bw=self.provision(b,"bob")
        self.assertEqual(self.post(self.b,ap,bc,
            headers={"X-Owner-ID":a}).status_code,404)
        self.assertEqual(aw.starts,0)
        self.assertEqual(bw.starts,0)
        self.assertEqual(self.post(self.a,ap,"bogus").status_code,403)
        self.assertEqual(self.post(self.a,ap,ac).status_code,200)
        self.assertEqual(self.post(self.b,bp,bc).status_code,200)
        self.assertEqual((aw.starts,bw.starts),(1,1))
        self.assertEqual(self.a.get("/urano/v1/runtime/state",
                                    base_url=HOST).json["state"],"ready")
        self.assertEqual(self.b.get("/urano/v1/runtime/state",
                                    base_url=HOST).json["state"],"ready")
        # The non-owner cannot read Stage or handoff, even if a worker runs.
        self.assertEqual(self.b.get("/urano/v1/runtime/projects/"+ap+"/ingest",
                                    base_url=HOST).status_code,404)
        self.assertEqual(self.b.get("/urano/v1/runtime/projects/"+ap+"/companion-handoff",
                                    base_url=HOST).status_code,404)
        self.assertEqual(self.a.post("/urano/v1/runtime/close",base_url=HOST,
                                    headers={"Origin":HOST,"X-Urano-CSRF":ac}).status_code,200)
        self.assertIsNone(aw.process)
        self.assertIsNotNone(bw.process)
        self.assertEqual(self.a.post("/urano/v1/logout",base_url=HOST,
                                    headers={"Origin":HOST,"X-Urano-CSRF":ac}).status_code,200)
        self.assertEqual(self.a.get("/urano/v1/runtime/state",base_url=HOST).status_code,401)

    def test_opt_in_default_exposes_no_worker_controls(self):
        plain=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                   frozenset({"alpha@example.test"})),provider=self.google)
        routes={r.rule for r in plain.url_map.iter_rules()}
        self.assertFalse(any(route.startswith("/urano/v1/runtime/") for route in routes))
        self.assertFalse(any(route.startswith("/montara/uploads") for route in routes))
        self.assertFalse(any(route.startswith("/video-renders") for route in routes))

if __name__=="__main__":
    unittest.main()
