"""C5 private proxy intake: verified bytes are NOT certified original provenance."""
import hashlib
import json
from pathlib import Path

from test_c4_owner_dashboard import TestC4OwnerDashboard
from test_google_flow_contract import CLIENT, CALLBACK, HOST
from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api


class TestC5PrivateProxyInbox(TestC4OwnerDashboard):
    def setUp(self):
        super().setUp()
        self.staging=self.root/"staged-proxies"
        self.staging.mkdir()
        self.app=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                       frozenset({"alpha@example.test","beta@example.test"})),
            provider=self.google,enable_dashboard=True,
            proxy_staging_root=self.staging)
        self.a,self.b=self.app.test_client(),self.app.test_client()

    def setup_project(self, client):
        result=client.post("/urano/v1/projects",base_url=HOST,
            headers={"Origin":HOST,"X-Urano-CSRF":self.csrf(client)},
            json={"title":"Private proxy project"})
        self.assertEqual(result.status_code,201)
        return result.json["project"]["id"]

    def send_proxy(self, client, project, payload, *, csrf=None, digest=None,
                   origin=HOST, claim=None, slot=0):
        identity=claim or {"name":"original.mp4","size":250000,"fingerprint":"a"*64}
        return client.put(f"/urano/v1/proxy-inbox/projects/{project}/slots/{slot}",
            base_url=HOST,data=payload,content_type="video/mp4",
            headers={"Origin":origin,
                     "X-Urano-CSRF":csrf or "",
                     "X-Urano-Original-Claim":json.dumps(identity),
                     "X-Urano-Proxy-SHA256":digest or hashlib.sha256(payload).hexdigest()})

    def test_opt_in_owner_and_digest_with_unattested_result(self):
        self.login(self.a,"proxy-alice","alpha@example.test")
        self.login(self.b,"proxy-bob","beta@example.test")
        project_a=self.setup_project(self.a)
        project_b=self.setup_project(self.b)
        csrf_a=self.csrf(self.a)
        csrf_b=self.csrf(self.b)
        video=b"synthetic-proxy-not-a-real-video"*700
        route=f"/urano/v1/proxy-inbox/projects/{project_a}/slots/0"
        self.assertEqual(self.b.get(route,base_url=HOST).status_code,405)
        self.assertEqual(self.send_proxy(self.b,project_a,video,csrf=csrf_b).status_code,404)
        self.assertEqual(self.send_proxy(self.a,project_b,video,csrf=csrf_a).status_code,404)
        self.assertEqual(self.send_proxy(self.a,project_a,video).status_code,403)
        self.assertEqual(self.send_proxy(self.a,project_a,video,csrf=csrf_a,
                                        origin="https://wrong.example").status_code,403)
        self.assertEqual(self.send_proxy(self.a,project_a,video,csrf=csrf_a,
                                        digest="0"*64).status_code,422)
        self.assertEqual(self.send_proxy(self.a,project_a,video,csrf=csrf_a,
                                        claim={"name":"../../original.mov","size":1,
                                               "fingerprint":"a"*64}).status_code,400)
        valid=self.send_proxy(self.a,project_a,video,csrf=csrf_a)
        self.assertEqual(valid.status_code,201,valid.get_data(as_text=True))
        self.assertIs(valid.json["attested"],False)
        self.assertEqual(valid.json["bytes"],len(video))
        self.assertNotIn("path",str(valid.json))
        files=list(self.staging.rglob("*.mp4"))
        self.assertEqual(len(files),1)
        self.assertEqual(files[0].read_bytes(),video)
        self.assertNotIn("original",files[0].name)
        metadata=list(self.staging.rglob("*.json"))
        self.assertEqual(len(metadata),1)
        record=json.loads(metadata[0].read_text())
        self.assertIs(record["attested"],False)
        self.assertEqual(record["proxy_sha256"],hashlib.sha256(video).hexdigest())
        self.assertEqual(list(self.staging.rglob("*.part")),[])

    def test_disabled_by_default_and_no_original_upload(self):
        plain=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                       frozenset({"alpha@example.test"})),provider=self.google)
        self.assertFalse(any(x.rule.startswith("/urano/v1/proxy-inbox")
                             for x in plain.url_map.iter_rules()))
        self.assertFalse(any("/montara/uploads" in x.rule
                             for x in self.app.url_map.iter_rules()))
        self.assertEqual(self.a.put("/urano/v1/proxy-inbox/projects/invalid/slots/0",
                                    base_url=HOST).status_code,401)
