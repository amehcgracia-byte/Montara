"""Attested source provenance is trusted-only and never browser-writable."""
from test_c5_private_workspace import TestC5PrivateWorkspace
from test_google_flow_contract import HOST, CALLBACK, CLIENT
from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from urano.stage_source_provenance import StageSourceProvenance, UnverifiedSources


class TestC5StageSourceProvenance(TestC5PrivateWorkspace):
    def setUp(self):
        super().setUp()
        self.provenance=StageSourceProvenance(self.root/"provenance.sqlite3",self.catalog)
        self.app=create_owner_api(
            self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                                  frozenset({"alpha@example.test","beta@example.test"})),
            provider=self.google,runtime_controller=self.controller,
            enable_dashboard=True,stage_provenance=self.provenance)
        self.a,self.b=self.app.test_client(),self.app.test_client()

    def test_provenance_fail_closed_until_trusted_attestation(self):
        owner_a,csrf_a=self.login(self.a,sub="google-stage-a",email="alpha@example.test")
        owner_b,csrf_b=self.login(self.b,sub="google-stage-b",email="beta@example.test")
        project_a,_=self.provision(owner_a,"alice")
        project_b,_=self.provision(owner_b,"bob")
        endpoint="/urano/v1/runtime/projects/"+project_a+"/verified-sources"
        self.assertEqual(self.a.get(endpoint,base_url=HOST).status_code,409)
        self.assertEqual(self.b.get(endpoint,base_url=HOST).status_code,409)
        self.assertEqual(self.a.post(endpoint,base_url=HOST,json={"sources":[]}).status_code,405)
        self.assertEqual(self.a.put(endpoint,base_url=HOST,json={"sources":[]}).status_code,405)
        self.assertEqual(self.a.get("/urano/v1/runtime/projects/"+project_b+"/verified-sources",base_url=HOST).status_code,409)

        cuts=[{"source_slot":0,"start_ms":100,"end_ms":2300}]
        put=self.a.put("/urano/v1/runtime/projects/"+project_a+"/edits",
                      base_url=HOST,headers={"Origin":HOST,"X-Urano-CSRF":csrf_a},
                      json={"cuts":cuts,"expected_revision":0})
        self.assertEqual(put.status_code,200,put.get_data(as_text=True))
        self.assertEqual(self.a.get(endpoint,base_url=HOST).status_code,409)

        identity={"name":"camera.mp4","size":123456,"fingerprint":"a"*64}
        sources=[{"source_slot":0,"original":identity}]
        with self.assertRaises(UnverifiedSources):
            self.provenance.register_trusted(owner_a,project_a,
                [{"source_slot":0,"original":{**identity,"name":"../../other.mp4"}}],
                stage_revision="b"*64)
        self.provenance.register_trusted(owner_a,project_a,sources,stage_revision="b"*64)
        accepted=self.a.get(endpoint,base_url=HOST)
        self.assertEqual(accepted.status_code,200)
        self.assertEqual(accepted.json["project_revision"],1)
        self.assertEqual(accepted.json["sources"],sources)
        self.assertEqual(accepted.json["stage_revision"],"b"*64)
        self.assertNotIn("path",str(accepted.json))
        self.assertEqual(self.b.get(endpoint,base_url=HOST).status_code,409)

        self.a.put("/urano/v1/runtime/projects/"+project_a+"/edits",
                   base_url=HOST,headers={"Origin":HOST,"X-Urano-CSRF":csrf_a},
                   json={"cuts":[{"source_slot":1,"start_ms":0,"end_ms":500}],
                         "expected_revision":1})
        self.assertEqual(self.a.get(endpoint,base_url=HOST).status_code,409)

    def test_unauthenticated_or_unknown_provenance_denied(self):
        self.assertEqual(self.a.get("/urano/v1/runtime/projects/any/verified-sources",
                                    base_url=HOST).status_code,401)
        self.assertEqual(self.a.get("/urano/v1/runtime/projects/any/verified-sources",
                                    base_url="http://lab.example.test").status_code,401)
