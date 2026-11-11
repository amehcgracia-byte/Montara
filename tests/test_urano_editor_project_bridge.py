"""I30 owner project choices integration tests: no extra UI or live Engine."""
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.editor_project_bridge import editor_project_bridge_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore


class EditorProjectBridgeTests(unittest.TestCase):
    ORIGIN = "https://montara-owner.example.test"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.catalog = ProjectCatalog(root / "projects.sqlite3")
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.stage = self.create("alice", "Stage A", "stage")
        self.push = self.create("alice", "Push A", "push")
        self.show = self.create("alice", "Show A", "show")
        self.foreign = self.create("bob", "Other user's Stage", "stage")
        self.unassigned = self.catalog.create("alice", "Legacy without mode")
        self.alice_session = self.sessions.issue("alice")
        self.bob_session = self.sessions.issue("bob")
        app = Flask("editor-project-bridge-test")
        app.register_blueprint(editor_project_bridge_blueprint(
            self.catalog, self.sessions, https_origin=self.ORIGIN))
        self.client = app.test_client()
        self.login(self.alice_session.token)

    def create(self, owner, title, mode):
        p = self.catalog.create(owner, title)
        return self.catalog.save_recipe(
            owner, p.id,
            {"montara_beta_workspace": {"version": 1, "mode": mode}},
            expected_revision=0,
        )

    def login(self, token):
        self.client.set_cookie(SESSION_COOKIE, token, domain="montara-owner.example.test")

    def get(self, path):
        return self.client.get("/urano/v1/editor/" + path, base_url=self.ORIGIN)

    def test_each_mode_shows_only_its_own_projects(self):
        for mode, wanted in [("stage", self.stage), ("push", self.push), ("show", self.show)]:
            with self.subTest(mode=mode):
                response = self.get("projects?mode=" + mode)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([x["id"] for x in response.json["projects"]], [wanted.id])
                self.assertNotIn("recipe", response.get_data(as_text=True))
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_mode_mismatch_and_foreign_project_are_both_hidden(self):
        for id_, mode in [(self.foreign.id, "stage"), (self.stage.id, "show"),
                          (self.unassigned.id, "stage"), ("../invalid", "stage")]:
            with self.subTest(id=id_, mode=mode):
                self.assertEqual(
                    self.get("projects/" + id_ + "?mode=" + mode).status_code, 404
                )
        response = self.get("projects/" + self.stage.id + "?mode=stage")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["project"]["id"], self.stage.id)

    def test_owner_is_taken_only_from_session(self):
        self.login(self.bob_session.token)
        result = self.client.get(
            "/urano/v1/editor/projects?mode=stage", base_url=self.ORIGIN,
            headers={"X-Owner-ID": "alice"},
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual([x["id"] for x in result.json["projects"]], [self.foreign.id])
        self.assertEqual(self.get("projects/" + self.stage.id + "?mode=stage").status_code, 404)

    def test_create_from_mode_is_owner_scoped_and_atomic(self):
        csrf = self.sessions.issue("alice")
        self.login(csrf.token)
        response = self.client.post(
            "/urano/v1/editor/projects", base_url=self.ORIGIN,
            headers={"Origin": self.ORIGIN, "X-Urano-CSRF": csrf.csrf},
            json={"title": "Nueva sesión", "mode": "push"},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        item = response.json["project"]
        self.assertEqual(item["mode"], "push")
        self.assertEqual(item["revision"], 0)
        saved = self.catalog.get("alice", item["id"])
        self.assertEqual(saved.recipe["montara_beta_workspace"]["mode"], "push")
        self.assertEqual(saved.revision, 0)
        self.assertEqual(self.catalog.list_for("bob"), [self.foreign])
        self.assertIn(item["id"], [
            p["id"] for p in self.get("projects?mode=push").json["projects"]
        ])

    def test_create_rejects_forged_owner_csrf_and_invalid_mode(self):
        valid = self.sessions.issue("alice")
        self.login(valid.token)
        url = "/urano/v1/editor/projects"
        initial = len(self.catalog.list_for("alice"))
        cases = [
            ({"Origin": self.ORIGIN}, {"title": "No CSRF", "mode": "stage"}),
            ({"Origin": "https://evil.test", "X-Urano-CSRF": valid.csrf},
             {"title": "Wrong origin", "mode": "stage"}),
            ({"Origin": self.ORIGIN, "X-Urano-CSRF": valid.csrf},
             {"title": "Wrong mode", "mode": "music"}),
            ({"Origin": self.ORIGIN, "X-Urano-CSRF": valid.csrf},
             {"title": "With owner", "mode": "stage", "owner_id": "bob"}),
            ({"Origin": self.ORIGIN, "X-Urano-CSRF": valid.csrf},
             {"title": "", "mode": "show"}),
        ]
        for headers, payload in cases:
            with self.subTest(payload=payload):
                self.assertIn(
                    self.client.post(url, base_url=self.ORIGIN,
                                     headers=headers, json=payload).status_code,
                    (400, 403),
                )
        self.assertEqual(len(self.catalog.list_for("alice")), initial)

    def test_missing_session_wrong_origin_invalid_mode_and_mutation(self):
        self.assertEqual(self.get("projects?mode=music").status_code, 400)
        self.assertEqual(self.get("projects").status_code, 400)
        self.assertEqual(self.client.post(
            "/urano/v1/editor/projects?mode=stage",
            base_url=self.ORIGIN, json={"title": "not allowed"}).status_code, 403)
        self.assertEqual(self.client.get(
            "/urano/v1/editor/projects?mode=stage",
            base_url="https://wrong.example.test").status_code, 403)
        self.sessions.revoke(self.alice_session.token)
        self.assertEqual(self.get("projects?mode=stage").status_code, 401)


if __name__ == "__main__":
    unittest.main()
