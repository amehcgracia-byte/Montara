"""I28 private editor workspace: real owner-scoped recipe persistence."""
import tempfile
import unittest
from pathlib import Path

from flask import Flask
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore,SESSION_COOKIE
from urano.owner_editor_workspace import workspace_blueprint


class I28WorkspaceTests(unittest.TestCase):
    HOST="https://montara-example.invalid"
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.catalog=ProjectCatalog(root/"projects.sqlite")
        self.sessions=SessionStore(root/"sessions.sqlite")
        self.a=self.catalog.create("owner-a","Mis canciones")
        self.b=self.catalog.create("owner-b","Proyecto ajeno")
        self.session=self.sessions.issue("owner-a")
        self.app=Flask("i28-workspace")
        self.app.register_blueprint(workspace_blueprint(
            self.catalog,self.sessions,https_origin=self.HOST))
        self.client=self.app.test_client()
        self.client.set_cookie(SESSION_COOKIE,self.session.token,domain="montara-example.invalid")

    def url(self,pid):
        return "/urano/v1/workspace?project="+pid

    def test_owner_can_open_workspace_and_download_assets(self):
        res=self.client.get(self.url(self.a.id),base_url=self.HOST)
        self.assertEqual(res.status_code,200)
        self.assertIn(b"Tu proyecto",res.data)
        self.assertIn(b"no-store",res.headers["Cache-Control"].encode())
        self.assertIn("frame-ancestors 'none'",res.headers["Content-Security-Policy"])
        for name,content in (("workspace.css",b".studio"),("workspace.js",b"expected_revision")):
            sub=self.client.get("/urano/v1/"+name,base_url=self.HOST)
            self.assertEqual(sub.status_code,200)
            self.assertIn(content,sub.data)

    def test_foreign_project_is_hidden(self):
        res=self.client.get(self.url(self.b.id),base_url=self.HOST)
        self.assertEqual(res.status_code,404)
        self.assertNotIn(self.b.title.encode(),res.data)

    def test_unauthenticated_user_cannot_access_editor(self):
        self.sessions.revoke(self.session.token)
        for path in (self.url(self.a.id),"/urano/v1/workspace.js","/urano/v1/workspace.css"):
            with self.subTest(path=path):
                res=self.client.get(path,base_url=self.HOST)
                self.assertEqual(res.status_code,401)

    def test_wrong_host_rejected(self):
        res=self.client.get(self.url(self.a.id),base_url="https://example.org")
        self.assertEqual(res.status_code,403)

    def test_invalid_project_id_rejected(self):
        res=self.client.get(self.url("../../etc/passwd"),base_url=self.HOST)
        self.assertEqual(res.status_code,404)

    def test_recipe_changes_preserve_original_keys_and_revision(self):
        original={"existing":{"engine":"untouched"}}
        first=self.catalog.save_recipe("owner-a",self.a.id,original,expected_revision=0)
        recipe={**first.recipe,"montara_beta_workspace":{
            "version":1,"mode":"stage","format":"landscape",
            "notes":"Cuatro camaras","blocks":["Intro","Solo de guitarra"]}}
        updated=self.catalog.save_recipe("owner-a",self.a.id,recipe,
                                         expected_revision=first.revision)
        again=ProjectCatalog(self.catalog.db_path).get("owner-a",self.a.id)
        self.assertEqual(again.recipe["existing"],original["existing"])
        self.assertEqual(again.recipe["montara_beta_workspace"]["blocks"][1],"Solo de guitarra")
        self.assertEqual(again.revision,updated.revision)
        self.assertEqual(again.revision,2)


if __name__=="__main__":
    unittest.main()

