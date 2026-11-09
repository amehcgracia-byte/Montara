"""C5 private cut plan -> revisioned catalog -> local Companion descriptor."""
from test_c5_private_workspace import TestC5PrivateWorkspace
from test_google_flow_contract import HOST


class TestC5PrivateCutPlan(TestC5PrivateWorkspace):
    def test_owned_cut_plan_revision_handoff_and_cross_user_denial(self):
        owner_a,csrf_a=self.login(self.a,sub="google-a-cuts",email="alpha@example.test")
        owner_b,csrf_b=self.login(self.b,sub="google-b-cuts",email="beta@example.test")
        project_a,_=self.provision(owner_a,"alice")
        project_b,_=self.provision(owner_b,"bob")
        route="/urano/v1/runtime/projects/"+project_a+"/edits"
        plan_url="/urano/v1/runtime/projects/"+project_a+"/companion-handoff"
        good={"expected_revision":0,"cuts":[{"source_slot":0,"start_ms":200,"end_ms":2700}]}
        origin={"Origin":HOST,"X-Urano-CSRF":csrf_a}
        self.assertEqual(self.b.put(route,base_url=HOST,headers={"Origin":HOST,"X-Urano-CSRF":csrf_b},json=good).status_code,404)
        self.assertEqual(self.a.put(route,base_url=HOST,json=good).status_code,403)
        self.assertEqual(self.a.put(route,base_url=HOST,headers=origin,
                         json={**good,"path":"/home/alpha"}).status_code,400)
        self.assertEqual(self.a.put(route,base_url=HOST,headers=origin,
                         json={"expected_revision":0,"cuts":[{"source_slot":0,"start_ms":200,"end_ms":2700,
                                                              "path":"/tmp/private.mov"}]}).status_code,400)
        self.assertEqual(self.a.put(route,base_url=HOST,headers=origin,
                         json={"expected_revision":0,"cuts":[{"source_slot":True,"start_ms":200,"end_ms":2700}]}).status_code,400)
        self.assertEqual(self.a.put(route,base_url=HOST,headers=origin,
                         json={"expected_revision":0,"cuts":[{"source_slot":0,"start_ms":200,"end_ms":999999999}]}).status_code,400)
        self.assertEqual(self.a.get(plan_url,base_url=HOST).status_code,409)
        created=self.a.put(route,base_url=HOST,headers=origin,json=good)
        self.assertEqual(created.status_code,200,created.get_data(as_text=True))
        self.assertEqual(created.json["revision"],1)
        self.assertIs(created.json["render_ready"],False)
        self.assertEqual(self.a.put(route,base_url=HOST,headers=origin,json=good).status_code,409)
        plan=self.a.get(plan_url,base_url=HOST)
        self.assertEqual(plan.status_code,200,plan.get_data(as_text=True))
        self.assertEqual(plan.json["plan"]["cuts"],good["cuts"])
        self.assertEqual(plan.json["plan"]["project_revision"],1)
        self.assertIs(plan.json["plan"]["render_ready"],False)
        self.assertIs(plan.json["plan"]["local_source_resolution_verified"],False)
        self.assertEqual(self.b.get(plan_url,base_url=HOST).status_code,404)
        self.assertEqual(self.a.get("/urano/v1/runtime/projects/"+project_b+"/companion-handoff",
                                    base_url=HOST).status_code,404)
        self.assertNotIn("/home/",str(plan.json))
        self.assertEqual(self.a.get("/api/v1/wizard/status",base_url=HOST).status_code,404)

    def test_existing_unrelated_recipe_is_preserved(self):
        owner,csrf=self.login(self.a,sub="google-old-recipe",email="alpha@example.test")
        project,_=self.provision(owner,"alice")
        self.catalog.save_recipe(owner,project,{"legacy":"untouched"},expected_revision=0)
        route="/urano/v1/runtime/projects/"+project+"/edits"
        result=self.a.put(route,base_url=HOST,headers={"Origin":HOST,"X-Urano-CSRF":csrf},
                          json={"expected_revision":1,"cuts":[{"source_slot":0,"start_ms":0,"end_ms":1000}]})
        self.assertEqual(result.status_code,409)
        self.assertEqual(self.catalog.get(owner,project).recipe,{"legacy":"untouched"})

    def test_browser_has_private_save_and_safe_descriptor_only(self):
        owner,_=self.login(self.a,sub="google-ui-cuts",email="alpha@example.test")
        project,_=self.provision(owner,"alice")
        html=self.a.get("/urano/v1/workspace/"+project,base_url=HOST)
        script=self.a.get("/urano/v1/workspace.js",base_url=HOST)
        self.assertEqual(html.status_code,200)
        self.assertEqual(script.status_code,200)
        self.assertIn('id="edit-cuts"',html.get_data(as_text=True))
        self.assertIn("companion-handoff",script.get_data(as_text=True))
        self.assertIn("expected_revision",script.get_data(as_text=True))
        self.assertNotIn("fetch('/api/v1/",script.get_data(as_text=True))
        self.assertIn('id="master-audio"',html.get_data(as_text=True))
        self.assertIn('id="export-local"',html.get_data(as_text=True))
        js=script.get_data(as_text=True)
        self.assertIn("startHandoffVideo(payload)",js)
        self.assertIn("verifiedOriginals.revision !== revision",js)
        self.assertIn("JSON.stringify(plan.cuts) !== JSON.stringify(cuts)",js)
        self.assertIn("montaraCompanion.saveInProject(folder.id,masterName,audio)",js)
        self.assertNotIn("fetch('/api/v1/",js)
        companion=self.a.get("/urano/v1/companion-client.js",base_url=HOST)
        self.assertEqual(companion.status_code,200)
        self.assertIn("'/video-renders/handoff'",companion.get_data(as_text=True))
