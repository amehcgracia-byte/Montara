"""U12b isolated lab interface and API, without touching Montara production."""
import tempfile
import unittest
from pathlib import Path

from urano.lab_app import create_isolated_lab_app


class LabDashboardContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = create_isolated_lab_app(Path(tmp.name))
        self.alice = self.app.test_client()
        self.bob = self.app.test_client()
        self.origin = {"Origin": "https://localhost"}

    def create_account(self, client, email):
        result = client.post("/urano/v1/register",
                             json={"email": email, "password": "laboratory-only-password"},
                             headers=self.origin)
        self.assertEqual(result.status_code, 201)
        return result.json["csrf"]

    def create_project(self, client, csrf, title):
        r = client.post("/urano/v1/projects", json={"title": title},
                        headers={"X-Urano-CSRF": csrf})
        self.assertEqual(r.status_code, 201)
        return r.json["project"]["id"]

    def test_ui_assets_served_only_by_opt_in_factory(self):
        page = self.alice.get("/urano-lab/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Mis proyectos", page.data)
        self.assertIn(b"loginTab", page.data)
        self.assertIn(b"frame-ancestors 'none'", page.headers["Content-Security-Policy"].encode())
        script = self.alice.get("/urano-lab/lab.js")
        self.assertEqual(script.status_code, 200)
        for endpoint in (b"/session/refresh", b"/projects", b"/logout", b"/login"):
            self.assertIn(endpoint, script.data)
        self.assertEqual(self.alice.get("/urano-lab/private").status_code, 404)
        self.assertEqual(self.alice.get("/urano-lab/../accounts.py").status_code, 404)

    def test_old_and_new_projects_return_and_foreign_project_stays_hidden(self):
        ac = self.create_account(self.alice, "alice@example.com")
        bc = self.create_account(self.bob, "bob@example.com")
        old = self.create_project(self.alice, ac, "Vídeo antiguo")
        recent = self.create_project(self.alice, ac, "Vídeo reciente")
        foreign = self.create_project(self.bob, bc, "Proyecto de Bob")
        alice_list = self.alice.get("/urano/v1/projects")
        ids = {item["id"] for item in alice_list.json["projects"]}
        self.assertEqual(ids, {old, recent})
        self.assertNotIn(foreign, ids)
        self.assertEqual(self.alice.get("/urano/v1/projects/" + foreign).status_code, 404)
        self.assertEqual(self.bob.get("/urano/v1/projects/" + old).status_code, 404)
        saved = self.alice.put("/urano/v1/projects/" + old + "/recipe",
                               json={"recipe": {"notes": "Trabajo guardado"}, "expected_revision": 0},
                               headers={"X-Urano-CSRF": ac})
        self.assertEqual(saved.status_code, 200)
        self.alice.post("/urano/v1/logout", json={}, headers={"X-Urano-CSRF": ac})
        self.assertEqual(self.alice.get("/urano/v1/projects").status_code, 401)
        fresh = self.app.test_client()
        login = fresh.post("/urano/v1/login",
                           json={"email": "alice@example.com", "password": "laboratory-only-password"},
                           headers=self.origin)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(fresh.get("/urano/v1/projects/" + old).json["project"]["recipe"]["notes"],
                         "Trabajo guardado")
        self.assertEqual({x["id"] for x in fresh.get("/urano/v1/projects").json["projects"]},
                         {old, recent})
        self.assertEqual(fresh.get("/urano/v1/projects/" + foreign).status_code, 404)

    def test_page_refresh_rotates_csrf_and_preserves_list(self):
        csrf = self.create_account(self.alice, "alice@example.com")
        old = self.create_project(self.alice, csrf, "Antiguo")
        refreshed = self.alice.post("/urano/v1/session/refresh", headers=self.origin)
        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(refreshed.json["csrf"], csrf)
        self.assertEqual(self.alice.post("/urano/v1/projects", json={"title": "CSRF viejo"},
                         headers={"X-Urano-CSRF": csrf}).status_code, 403)
        self.assertEqual(self.alice.get("/urano/v1/projects/" + old).status_code, 200)

    def test_app_is_never_mutated_by_factory_setup(self):
        self.assertFalse("MONTARA" in self.app.config)
        self.assertEqual(self.alice.get("/").status_code, 404)
        self.assertEqual(self.alice.get("/api/v1/wizard/status").status_code, 404)


if __name__ == "__main__":
    unittest.main()
