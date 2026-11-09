"""C5 first browser-to-owner Stage bridge, with no global Engine or media route."""
from urano.google_flow import OIDCSettings
from urano.minimal_owner_api import create_owner_api
from test_google_flow_contract import CLIENT, CALLBACK, SignedFakeGoogle, HOST
from test_c2_google_to_private_engine import FullOwnerToEngineIntegration


class TestC5PrivateWorkspace(FullOwnerToEngineIntegration):
    def setUp(self):
        super().setUp()
        self.app=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                                  frozenset({"alpha@example.test","beta@example.test"})),
            provider=self.google,runtime_controller=self.controller,enable_dashboard=True)
        self.a,self.b=self.app.test_client(),self.app.test_client()

    def test_owner_workspace_route_and_private_activation(self):
        self.assertEqual(self.a.get("/urano/v1/workspace.js",base_url=HOST).status_code,401)
        self.assertEqual(self.a.get("/urano/v1/workspace/foreign",base_url=HOST).status_code,401)
        owner_a,csrf_a=self.login(self.a,sub="google-sub-a",email="alpha@example.test")
        owner_b,csrf_b=self.login(self.b,sub="google-sub-b",email="beta@example.test")
        project_a,bridge_a=self.provision(owner_a,"alice")
        project_b,bridge_b=self.provision(owner_b,"bob")

        page=self.a.get("/urano/v1/workspace/"+project_a,base_url=HOST)
        self.assertEqual(page.status_code,200)
        self.assertIn("Stage y Engine aislados",page.get_data(as_text=True))
        self.assertEqual(page.headers["Cache-Control"],"no-store")
        self.assertIn("default-src 'none'",page.headers["Content-Security-Policy"])
        self.assertEqual(self.a.get("/urano/v1/workspace.js",base_url=HOST).status_code,200)
        self.assertEqual(self.a.get("/urano/v1/workspace/"+project_b,base_url=HOST).status_code,404)
        self.assertEqual(self.b.get("/urano/v1/workspace/"+project_a,base_url=HOST).status_code,404)
        self.assertEqual(self.b.get("/urano/v1/workspace/invalid",base_url=HOST).status_code,404)
        self.assertEqual(self.a.get("/urano/v1/workspace/"+project_a,
                     base_url="http://lab.example.test").status_code,403)
        self.assertEqual(self.a.get("/urano/v1/dashboard.js",base_url=HOST).status_code,200)
        self.assertIn("MONTARA_PRIVATE_RUNTIME = true",
                      self.a.get("/urano/v1/dashboard.js",base_url=HOST).get_data(as_text=True))

        self.assertEqual(self.post(self.b,project_a,csrf_b).status_code,404)
        self.assertEqual(bridge_a.starts,0)
        self.assertEqual(self.post(self.a,project_a,csrf_a).status_code,200)
        self.assertEqual(bridge_a.starts,1)
        self.assertEqual(bridge_b.starts,0)
        self.assertEqual(self.a.get("/urano/v1/runtime/state",base_url=HOST).json["state"],"ready")

        for route in ("/api/v1/wizard/status","/montara/uploads","/video-renders"):
            self.assertEqual(self.a.get(route,base_url=HOST).status_code,404)

    def test_without_runtime_no_stage_workspace(self):
        plain=create_owner_api(self.root,
            settings=OIDCSettings(CLIENT,"fake-secret-do-not-use",CALLBACK,
                         frozenset({"alpha@example.test"})),
            provider=SignedFakeGoogle(),enable_dashboard=True)
        routes={x.rule for x in plain.url_map.iter_rules()}
        self.assertNotIn("/urano/v1/workspace/<project_id>",routes)
        self.assertNotIn("/urano/v1/workspace.js",routes)
        self.assertEqual(plain.test_client().get("/urano/v1/workspace/any",base_url=HOST).status_code,404)
