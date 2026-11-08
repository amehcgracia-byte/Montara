"""Offline Google OIDC security contracts. All signing keys/identities are synthetic."""
from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from urano.google_oidc import GoogleIdentityDenied, verify_google_id_token
from urano.google_owner import GoogleOwnerStore
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.session_auth import SessionStore

CLIENT = "synthetic-client.apps.googleusercontent.com"
NONCE = "synthetic-high-entropy-nonce-123456789"
NOW = 1800000000


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class GoogleOIDCContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = cls.key.public_key().public_numbers()
        cls.jwks = {"keys": [{
            "kid": "synthetic-key-1", "kty": "RSA", "use": "sig", "alg": "RS256",
            "n": b64(public.n.to_bytes((public.n.bit_length() + 7) // 8, "big")),
            "e": b64(public.e.to_bytes((public.e.bit_length() + 7) // 8, "big")),
        }]}

    def token(self, *, claims=None, header=None):
        body = {"iss": "https://accounts.google.com", "aud": CLIENT, "sub": "stable-google-sub-123",
                "nonce": NONCE, "exp": NOW + 3600, "iat": NOW - 20,
                "email": "alpha@example.test", "email_verified": True}
        body.update(claims or {})
        head = {"kid": "synthetic-key-1", "alg": "RS256", "typ": "JWT"}
        head.update(header or {})
        signing_input = b64(json.dumps(head, separators=(",", ":")).encode()) + "." + b64(
            json.dumps(body, separators=(",", ":")).encode())
        signature = self.key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return signing_input + "." + b64(signature)

    def verify(self, token=None, **overrides):
        options = {"client_id": CLIENT, "expected_nonce": NONCE, "jwks": self.jwks, "now": NOW}
        options.update(overrides)
        return verify_google_id_token(self.token() if token is None else token, **options)

    def test_verified_google_sub_and_email(self):
        identity = self.verify()
        self.assertEqual(identity.sub, "stable-google-sub-123")
        self.assertEqual(identity.email, "alpha@example.test")

    def test_signature_tampering_and_algorithm_confusion_fail(self):
        token = self.token()
        a, b, c = token.split(".")
        with self.assertRaises(GoogleIdentityDenied):
            self.verify(a + "." + b + "." + b64(b"not-a-real-signature"))
        for header in ({"alg": "none"}, {"alg": "HS256"}, {"kid": "no-such-key"}):
            with self.subTest(header=header), self.assertRaises(GoogleIdentityDenied):
                self.verify(self.token(header=header))

    def test_nonce_issuer_client_and_azp_rejected(self):
        cases = ({"nonce": "other-nonce-123456789"}, {"iss": "https://malicious.example"},
                 {"aud": "wrong-client"}, {"aud": [CLIENT, "another"], "azp": "another"},
                 {"aud": CLIENT, "azp": "another"})
        for claim in cases:
            with self.subTest(claim=claim), self.assertRaises(GoogleIdentityDenied):
                self.verify(self.token(claims=claim))

    def test_multiple_audiences_require_matching_azp(self):
        self.verify(self.token(claims={"aud": [CLIENT, "another"], "azp": CLIENT}))

    def test_expiration_future_issue_and_unverified_email_fail(self):
        for claims in ({"exp": NOW - 65}, {"iat": NOW + 65},
                       {"email_verified": False}, {"email_verified": "true"},
                       {"sub": ""}, {"exp": "1800003600"}):
            with self.subTest(claims=claims), self.assertRaises(GoogleIdentityDenied):
                self.verify(self.token(claims=claims))

    def test_malformed_jwks_duplicate_kid_and_wrong_client_fail(self):
        for jwks in ({"keys": []}, {"keys": self.jwks["keys"] * 2},
                     {"keys": [{**self.jwks["keys"][0], "alg": "HS256"}]}):
            with self.subTest(jwks=jwks), self.assertRaises(GoogleIdentityDenied):
                self.verify(jwks=jwks)
        with self.assertRaises(GoogleIdentityDenied):
            self.verify(client_id="other-client")
        with self.assertRaises(GoogleIdentityDenied):
            self.verify(expected_nonce="short")

    def test_google_subjects_keep_separate_project_histories_and_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owners = GoogleOwnerStore(root / "google.sqlite3")
            projects = ProjectCatalog(root / "projects.sqlite3")
            sessions = SessionStore(root / "sessions.sqlite3")
            allowed = frozenset({"alpha@example.test"})
            a = self.verify()
            b = self.verify(self.token(claims={"sub": "another-google-sub-888"}))
            owner_a = owners.resolve_beta_owner(a, allowed_emails=allowed)
            owner_b = owners.resolve_beta_owner(b, allowed_emails=allowed)
            project_a = projects.create(owner_a, "A's older project")
            project_b = projects.create(owner_b, "B's independent project")
            session_a = sessions.issue(owner_a)
            session_b = sessions.issue(owner_b)
            self.assertNotEqual(session_a.token, session_b.token)
            self.assertEqual(sessions.verify(session_a.token).owner_id, owner_a)
            self.assertEqual(sessions.verify(session_b.token).owner_id, owner_b)
            self.assertEqual([p.id for p in projects.list_for(owner_a)], [project_a.id])
            self.assertEqual([p.id for p in projects.list_for(owner_b)], [project_b.id])
            with self.assertRaises(ProjectNotFound):
                projects.get(owner_b, project_a.id)
            with self.assertRaises(ProjectNotFound):
                projects.get(owner_a, project_b.id)
            sessions.revoke(session_a.token)
            self.assertIsNone(sessions.verify(session_a.token))
            self.assertIsNotNone(sessions.verify(session_b.token))
            self.assertEqual(
                GoogleOwnerStore(root / "google.sqlite3").resolve_beta_owner(a, allowed_emails=allowed),
                owner_a,
            )

    def test_beta_allowlist_and_sub_isolation_across_database_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "beta.sqlite3"
            store = GoogleOwnerStore(db)
            allow = frozenset({"alpha@example.test"})
            identity = self.verify()
            owner1 = store.resolve_beta_owner(identity, allowed_emails=allow)
            owner2 = GoogleOwnerStore(db).resolve_beta_owner(identity, allowed_emails=allow)
            self.assertEqual(owner1, owner2)
            other_identity = self.verify(self.token(claims={"sub": "different-google-sub"}))
            self.assertNotEqual(owner1, store.resolve_beta_owner(other_identity, allowed_emails=allow))
            with self.assertRaises(GoogleIdentityDenied):
                store.resolve_beta_owner(identity, allowed_emails=frozenset({"other@example.test"}))
            other_email = self.verify(self.token(claims={"email": "other@example.test"}))
            with self.assertRaises(GoogleIdentityDenied):
                store.resolve_beta_owner(other_email, allowed_emails=allow)
            with self.assertRaises(GoogleIdentityDenied):
                store.resolve_beta_owner({"sub": identity.sub}, allowed_emails=allow)


if __name__ == "__main__":
    unittest.main()
