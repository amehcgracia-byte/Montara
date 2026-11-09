"""C8 private preview: one real editor process, no Docker and no public listener.

Fixtures never install services, run the actual Engine or provision a server.
"""
import contextlib
import importlib
import io
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
import deploy.personal_beta as beta


class PersonalBetaGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-c8-private-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "operator"
        self.home.mkdir(mode=0o700)
        self.repo = self.base / "test-repository"
        (self.repo/"engine"/"server").mkdir(parents=True)
        (self.repo/"mixer").mkdir()
        (self.repo/"engine"/"server"/"api.py").write_text("pass")
        (self.repo/"mixer"/"jam_mix_pipeline.py").write_text("pass")
        self.old_root = beta.ROOT
        beta.ROOT = self.repo
        self.addCleanup(lambda: setattr(beta, "ROOT", self.old_root))
        self.data, self.config = beta._default_locations(self.home)
        self.data.mkdir(mode=0o700)
        self.config.parent.mkdir(parents=True,mode=0o700)
        self.config.write_text(json.dumps({
            "username": "montara", "password": "private-demo-secret-test-123"
        }),encoding="utf-8")
        self.config.chmod(0o600)

    def check(self, port=18114):
        return beta.check_private_beta(
            self.data,self.config,home=self.home,port=port)

    def test_private_single_user_profile_explicitly_not_multiuser_or_public(self):
        result=self.check()
        self.assertTrue(result["ready_for_single_user_tunnel"])
        self.assertFalse(result["multiowner_isolation"])
        self.assertFalse(result["public_https_deployed"])
        self.assertNotIn("private-demo-secret",json.dumps(result))
        self.assertNotIn(str(self.home),json.dumps(result))

    def test_shared_or_existing_application_ports_are_rejected(self):
        for port in (8101,8102,8103,8090,80,443,65536,-1):
            with self.subTest(port=port),self.assertRaises(ValueError):
                self.check(port=port)

    def test_wrong_file_permissions_or_foreign_data_rejected(self):
        self.config.chmod(0o644)
        with self.assertRaises(ValueError):
            self.check()
        self.config.chmod(0o600)
        self.data.chmod(0o755)
        with self.assertRaises(ValueError):
            self.check()
        self.data.chmod(0o700)
        rogue=self.base/"foreign"
        rogue.mkdir()
        with self.assertRaises(ValueError):
            beta.check_private_beta(rogue,self.config,home=self.home,port=18114)

    def test_existing_zucker_data_not_accepted(self):
        source=self.home/"ZuckerVideos"
        source.mkdir(mode=0o700)
        with self.assertRaises(ValueError):
            beta.check_private_beta(source,self.config,home=self.home,port=18114)

    def test_password_reject_and_no_docker_or_systemd_calls(self):
        self.config.write_text(json.dumps({
            "username":"montara","password":"short"}))
        with self.assertRaises(ValueError):
            self.check()
        self.assertNotIn("docker",beta.__doc__.split("Use --init")[0].lower().replace("no docker",""))

    def test_generated_credentials_permissions_and_no_secret_stdout(self):
        self.config.unlink()
        self.data.rmdir()
        captured=io.StringIO()
        with patch.object(beta.getpass,"getpass",
                          return_value="valid-password-not-in-stdout"):
            with contextlib.redirect_stdout(captured):
                beta.init_private_beta(self.data,self.config,home=self.home)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(self.data.stat().st_mode),0o700)
        self.assertNotIn("valid-password-not-in-stdout",captured.getvalue())
        with self.assertRaises(ValueError):
            beta.init_private_beta(self.data,self.config,home=self.home)


class ExistingPreviewAuthentication(unittest.TestCase):
    def test_basic_auth_is_real_and_does_not_require_docker(self):
        fake=types.ModuleType("app")
        def factory(path):
            app=Flask("private-beta-stub")
            app.add_url_rule("/","index",lambda:"MONTARA C8")
            return app
        fake.create_montara_app=factory
        with patch.dict(sys.modules,{"app":fake}):
            with patch.dict(os.environ,{
                "MONTARA_PREVIEW_PASSWORD":"private-preview-secret-123",
                "MONTARA_PREVIEW_USER":"montara",
                "MONTARA_DATA":"/tmp/fake-private-c8",
            }):
                sys.modules.pop("deploy.entry",None)
                preview=importlib.import_module("deploy.entry")
                self.addCleanup(lambda:sys.modules.pop("deploy.entry",None))
        client=preview.app.test_client()
        self.assertEqual(client.get("/").status_code,401)
        wrong=client.get("/",headers={"Authorization":"Basic d3Jvbmc6d3Jvbmc="})
        self.assertEqual(wrong.status_code,401)
        from base64 import b64encode
        authorized=b64encode(b"montara:private-preview-secret-123").decode()
        response=client.get("/",headers={"Authorization":"Basic "+authorized})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_data(as_text=True),"MONTARA C8")
        self.assertEqual(response.headers.get("X-Robots-Tag"),"noindex, nofollow")


if __name__=="__main__":
    unittest.main()
