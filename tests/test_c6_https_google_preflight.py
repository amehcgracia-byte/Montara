"""C6: exact HTTPS origin / real Google configuration are fail-closed.

Uses fake credentials and a disposable companion home; never calls Google.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from urano.c6_beta_preflight import validate_beta_origin, validate_beta_settings


class C6BetaPreflight(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-c6-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.secret = self.root / "private-google-secret"
        self.secret.write_text("test-only-google-oauth-secret")
        self.secret.chmod(0o600)
        self.base = {
            "MONTARA_BETA_ORIGIN": "https://beta.example.test",
            "MONTARA_COMPANION_BETA_ORIGIN": "https://beta.example.test",
            "MONTARA_GOOGLE_CLIENT_ID":
                "123456789-demo-web-client.apps.googleusercontent.com",
            "MONTARA_BETA_ALLOWED_EMAILS": "alpha@example.test,beta@example.test",
            "MONTARA_GOOGLE_SECRET_FILE": str(self.secret),
        }

    def test_valid_settings_use_exact_google_callback_not_a_guess(self):
        config = validate_beta_settings(self.base)
        self.assertEqual(config.origin, "https://beta.example.test")
        self.assertEqual(config.settings.redirect_uri,
                         "https://beta.example.test/urano/v1/google/callback")
        self.assertEqual(config.settings.allowed_emails,
                         frozenset({"alpha@example.test", "beta@example.test"}))
        self.assertEqual(config.settings.client_secret,
                         "test-only-google-oauth-secret")

    def test_http_wildcards_url_components_and_localhost_denied(self):
        for origin in (
            "", "http://beta.example.test", "https://*.example.test",
            "https://beta.example.test/", "https://beta.example.test/a",
            "https://beta.example.test?x=1",
            "https://beta.example.test#x", "https://alice@beta.example.test",
            "https://localhost", "https://127.0.0.1",
            "https://beta.example.test:8443",
            "https://beta.example.test:443",
            "https://beta.example.test\\wrong",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_beta_origin(origin)

    def test_unpaired_companion_and_malformed_allowlist_rejected(self):
        for field, value in (
            ("MONTARA_COMPANION_BETA_ORIGIN", "https://other.example.test"),
            ("MONTARA_GOOGLE_CLIENT_ID", "google"),
            ("MONTARA_BETA_ALLOWED_EMAILS", "*"),
            ("MONTARA_BETA_ALLOWED_EMAILS", "alpha@example.test,alpha@example.test"),
            ("MONTARA_BETA_ALLOWED_EMAILS", "Alpha@example.test"),
            ("MONTARA_BETA_ALLOWED_EMAILS", ""),
        ):
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                validate_beta_settings({**self.base,field:value})

    def test_missing_world_readable_or_symlink_secret_denied(self):
        for filename in ("", "/missing/google-secret"):
            with self.assertRaises(ValueError):
                validate_beta_settings({**self.base,
                                        "MONTARA_GOOGLE_SECRET_FILE":filename})
        self.secret.chmod(0o644)
        with self.assertRaises(ValueError):
            validate_beta_settings(self.base)
        self.secret.chmod(0o600)
        linked=self.root/"linked-secret"
        linked.symlink_to(self.secret)
        with self.assertRaises(ValueError):
            validate_beta_settings({**self.base,"MONTARA_GOOGLE_SECRET_FILE":str(linked)})

    def test_companion_signed_receipt_only_for_exact_beta_origin(self):
        script=textwrap.dedent("""
            import os, sys
            from pathlib import Path
            from types import SimpleNamespace
            os.environ["MONTARA_COMPANION_HOME"]=str(Path(sys.argv[2])/"companion-home")
            sys.path.insert(0,sys.argv[1])
            import companion

            origin="https://beta.example.test"
            malicious="https://some-preview.vercel.app"
            assert not companion.trusted_signed_receipt_origin(origin)
            os.environ["MONTARA_COMPANION_BETA_ORIGIN"]=origin
            assert companion.trusted_signed_receipt_origin(origin)
            assert not companion.trusted_signed_receipt_origin(malicious)
            assert not companion.trusted_signed_receipt_origin("http://beta.example.test")
            assert not companion.trusted_signed_receipt_origin(origin+"/")
            accepted=SimpleNamespace(headers={"Origin":origin})
            accepted.origin_ok=lambda:companion.Handler.origin_ok(accepted)
            assert accepted.origin_ok()==origin
            denied=SimpleNamespace(headers={"Origin":malicious})
            denied.origin_ok=lambda:companion.Handler.origin_ok(denied)
            assert denied.origin_ok()==malicious
            # Legacy CORS may accept preview origins for non-sensitive routes,
            # but the signed-receipt GET must reject them before signing.
            denied.path="/proxies/"+("a"*24)+"/signed-receipt?project_id=x&slot=0"
            denied.reply=lambda status,body: (status,body)
            code,data=companion.Handler.do_GET(denied)
            assert code==403, (code,data)
            print("C6_COMPANION_EXACT_ORIGIN_PASS")
        """)
        with tempfile.TemporaryDirectory(prefix="montara-c6-companion-") as work:
            proc=subprocess.run(
                [sys.executable,"-c",script,
                 str(Path(__file__).resolve().parents[1]/"companion"),work],
                capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertIn("C6_COMPANION_EXACT_ORIGIN_PASS",proc.stdout)


if __name__ == "__main__":
    unittest.main()
