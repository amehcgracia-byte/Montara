"""U12: lab signup/login leads to U11 owner-protected project routes."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from urano.accounts import AccountStore, LoginDenied
from urano.http_auth import auth_blueprint
from urano.http_projects import project_blueprint
from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore


class UranoLabAuthContract(unittest.TestCase):
    ORIGIN = {"Origin": "https://localhost"}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.accounts = AccountStore(root / "accounts.sqlite3")
        self.sessions = SessionStore(root / "sessions.sqlite3")
        self.projects = ProjectCatalog(root / "projects.sqlite3")
        self.app = Flask(__name__)
        self.app.register_blueprint(auth_blueprint(self.accounts, self.sessions))
        self.app.register_blueprint(project_blueprint(self.projects, self.sessions))
        self.a = self.app.test_client()
        self.b = self.app.test_client()

    def register(self, client, email, password="a-very-long-lab-password"):
        return client.post("/urano/v1/register", json={"email": email, "password": password},
                           headers=self.ORIGIN)

    def login(self, client, email, password="a-very-long-lab-password"):
        return client.post("/urano/v1/login", json={"email": email, "password": password},
                           headers=self.ORIGIN)

    def test_signup_and_login_own_projects_without_client_owner_id(self):
        alice = self.register(self.a, " Alice@Example.com ")
        bob = self.register(self.b, "bob@example.com")
        self.assertEqual((alice.status_code, bob.status_code), (201, 201))
        self.assertNotEqual(alice.json["csrf"], bob.json["csrf"])
        self.assertIn("Secure", alice.headers["Set-Cookie"])
        self.assertIn("HttpOnly", alice.headers["Set-Cookie"])
        a = self.a.post("/urano/v1/projects", json={"title": "Stage", "owner_id": "fake"},
                        headers={"X-Urano-CSRF": alice.json["csrf"]})
        b = self.b.post("/urano/v1/projects", json={"title": "Show"},
                        headers={"X-Urano-CSRF": bob.json["csrf"]})
        self.assertEqual((a.status_code, b.status_code), (201, 201))
        aid = a.json["project"]["id"]
        self.assertEqual(self.b.get("/urano/v1/projects/" + aid).status_code, 404)
        self.assertEqual(len(self.a.get("/urano/v1/projects").json["projects"]), 1)
        fresh = self.app.test_client()
        logged = self.login(fresh, "alice@example.com")
        self.assertEqual(logged.status_code, 200)
        self.assertEqual(fresh.get("/urano/v1/projects/" + aid).status_code, 200)

    def test_password_not_stored_as_plaintext_and_duplicate_email_rejected(self):
        self.assertEqual(self.register(self.a, "alice@example.com").status_code, 201)
        self.assertEqual(self.register(self.b, "ALICE@example.com").status_code, 409)
        with sqlite3.connect(self.accounts.db_path) as db:
            owner_id, salt, digest = db.execute(
                "SELECT owner_id,password_salt,password_hash FROM urano_accounts").fetchone()
        self.assertNotIn(b"a-very-long-lab-password", digest)
        self.assertEqual((len(salt), len(digest)), (16, 32))
        self.assertTrue(owner_id)

    def test_wrong_password_does_not_create_session(self):
        self.register(self.a, "alice@example.com")
        self.assertEqual(self.login(self.b, "alice@example.com", "wrong password").status_code, 401)
        self.assertEqual(self.b.get("/urano/v1/projects").status_code, 401)
        self.assertEqual(self.login(self.b, "missing@example.com", "wrong password").status_code, 401)

    def test_lockout_is_persisted_and_recovers_after_expiry(self):
        owner = self.accounts.register("someone@example.com", "very-long-test-password")
        for _ in range(5):
            with self.assertRaises(LoginDenied):
                self.accounts.verify("someone@example.com", "bad", now=1000)
        with self.assertRaises(LoginDenied):
            self.accounts.verify("someone@example.com", "very-long-test-password", now=1001)
        reopened = AccountStore(self.accounts.db_path)
        self.assertEqual(reopened.verify("someone@example.com", "very-long-test-password", now=2000), owner)

    def test_cross_origin_or_missing_origin_cannot_register_or_login(self):
        for origin in ({}, {"Origin": "https://attacker.example"}, {"Origin": "http://localhost"}):
            r = self.a.post("/urano/v1/register",
                            json={"email": "someone@example.com", "password": "long-safe-password"},
                            headers=origin)
            self.assertEqual(r.status_code, 403)
        self.assertEqual(self.a.get("/urano/v1/projects").status_code, 401)

    def test_session_refresh_restores_csrf_after_page_reload(self):
        registered = self.register(self.a, "alice@example.com")
        csrf_old = registered.json["csrf"]
        self.assertEqual(registered.status_code, 201)
        before = self.a.get("/urano/v1/projects")
        self.assertEqual(before.status_code, 200)
        refreshed = self.a.post("/urano/v1/session/refresh", headers=self.ORIGIN)
        self.assertEqual(refreshed.status_code, 200)
        csrf_new = refreshed.json["csrf"]
        self.assertNotEqual(csrf_new, csrf_old)
        self.assertEqual(refreshed.headers["Cache-Control"], "no-store")
        self.assertEqual(self.a.post("/urano/v1/projects", json={"title": "Outdated"},
                         headers={"X-Urano-CSRF": csrf_old}).status_code, 403)
        self.assertEqual(self.a.post("/urano/v1/projects", json={"title": "Restored"},
                         headers={"X-Urano-CSRF": csrf_new}).status_code, 201)
        self.assertEqual(self.a.post("/urano/v1/session/refresh",
                         headers={"Origin": "https://attacker.example"}).status_code, 403)
        self.assertEqual(self.b.post("/urano/v1/session/refresh", headers=self.ORIGIN).status_code, 401)

    def test_invalid_registration_rejected(self):
        self.assertEqual(self.register(self.a, "bad-email").status_code, 400)
        self.assertEqual(self.register(self.a, "bad@example.com", "short").status_code, 400)


if __name__ == "__main__":
    unittest.main()
