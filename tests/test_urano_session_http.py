"""Real HTTP test clients, fictitious identities; no login or network deployment."""
import tempfile
import time
import unittest
from pathlib import Path

from flask import Flask

from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SESSION_COOKIE, SessionStore, set_session_cookie


class UranoSessionHTTPContract(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.catalog = ProjectCatalog(root / "projects.sqlite3")
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.app = Flask(__name__)
        self.app.register_blueprint(project_blueprint(self.catalog, self.sessions))
        self.alice = self.sessions.issue("test:alice")
        self.bob = self.sessions.issue("test:bob")
        self.a = self.app.test_client()
        self.b = self.app.test_client()
        self.a.set_cookie(SESSION_COOKIE, self.alice.token, secure=True)
        self.b.set_cookie(SESSION_COOKIE, self.bob.token, secure=True)

    def post(self, client, url, body, session):
        return client.post(url, json=body, headers={"X-Urano-CSRF": session.csrf})

    def test_http_isolation_across_two_clients(self):
        a = self.post(self.a, "/urano/v1/projects", {"title": "Stage"}, self.alice)
        b = self.post(self.b, "/urano/v1/projects", {"title": "Show"}, self.bob)
        self.assertEqual((a.status_code, b.status_code), (201, 201))
        aid = a.json["project"]["id"]
        bid = b.json["project"]["id"]
        self.assertEqual([x["id"] for x in self.a.get("/urano/v1/projects").json["projects"]], [aid])
        self.assertEqual([x["id"] for x in self.b.get("/urano/v1/projects").json["projects"]], [bid])
        self.assertEqual(self.b.get(f"/urano/v1/projects/{aid}").status_code, 404)
        self.assertEqual(self.a.get(f"/urano/v1/projects/{bid}").status_code, 404)
        forbidden = self.b.put(f"/urano/v1/projects/{aid}/recipe",
                      json={"recipe": {"edit": "stolen"}, "expected_revision": 0},
                      headers={"X-Urano-CSRF": self.bob.csrf})
        self.assertEqual(forbidden.status_code, 404)

    def test_forged_owner_headers_and_body_do_not_impersonate(self):
        r = self.a.post("/urano/v1/projects", json={"title": "Only Alice", "owner_id": "test:bob"},
                        headers={"X-Urano-CSRF": self.alice.csrf, "X-User-ID": "test:bob"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.catalog.list_for("test:alice")), 1)
        self.assertEqual(self.catalog.list_for("test:bob"), [])

    def test_no_session_invalid_session_and_csrf_denied(self):
        self.assertEqual(self.app.test_client().get("/urano/v1/projects").status_code, 401)
        bad = self.app.test_client()
        bad.set_cookie(SESSION_COOKIE, "tampered", secure=True)
        self.assertEqual(bad.get("/urano/v1/projects").status_code, 401)
        self.assertEqual(self.a.post("/urano/v1/projects", json={"title": "No CSRF"}).status_code, 403)
        self.assertEqual(self.a.post("/urano/v1/projects", json={"title": "Wrong"},
                        headers={"X-Urano-CSRF": self.bob.csrf}).status_code, 403)
        self.assertEqual(self.catalog.list_for("test:alice"), [])

    def test_save_conflict_and_reload_catalog(self):
        pid = self.post(self.a, "/urano/v1/projects", {"title": "A"}, self.alice).json["project"]["id"]
        route = f"/urano/v1/projects/{pid}/recipe"
        first = self.a.put(route, json={"recipe": {"cuts": [3]}, "expected_revision": 0},
                           headers={"X-Urano-CSRF": self.alice.csrf})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.a.put(route, json={"recipe": {"cuts": [4]}, "expected_revision": 0},
                         headers={"X-Urano-CSRF": self.alice.csrf}).status_code, 409)
        self.assertEqual(ProjectCatalog(self.catalog.db_path).get("test:alice", pid).recipe, {"cuts": [3]})

    def test_logout_revokes_even_after_reopen(self):
        r = self.post(self.a, "/urano/v1/logout", {}, self.alice)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.a.get("/urano/v1/projects").status_code, 401)
        self.assertIsNone(SessionStore(self.sessions.db_path).verify(self.alice.token))

    def test_expiry_rejected_and_cookie_security_flags(self):
        issued = self.sessions.issue("test:short", ttl_seconds=1, now=int(time.time()) - 20)
        self.assertIsNone(self.sessions.verify(issued.token))
        r = self.app.response_class()
        set_session_cookie(r, self.alice)
        cookie = r.headers["Set-Cookie"]
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Path=/", cookie)
        self.assertNotIn("Domain=", cookie)

    def test_session_lookup_persists_after_store_reopened(self):
        reopened = SessionStore(self.sessions.db_path)
        self.assertEqual(reopened.verify(self.alice.token).owner_id, "test:alice")


if __name__ == "__main__":
    unittest.main()
