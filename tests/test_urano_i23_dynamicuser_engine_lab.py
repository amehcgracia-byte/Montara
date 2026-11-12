"""I23 offline safety contracts; does not invoke sudo/systemd."""
import ast
import sys
import unittest
from pathlib import Path

SOURCE=Path(__file__).parent/"urano_i23_dynamicuser_engine_lab.py"


class DynamicUserBundleContracts(unittest.TestCase):
    def test_only_operator_opt_in_can_launch(self):
        src=SOURCE.read_text()
        ast.parse(src)
        self.assertIn("--operator-opt-in",src)
        self.assertIn("if not args.operator_opt_in:",src)

    def test_systemd_security_boundaries(self):
        src=SOURCE.read_text()
        for token in ("DynamicUser=yes","ProtectHome=yes","PrivateNetwork=yes",
                      "NoNewPrivileges=yes","BindReadOnlyPaths=",
                      "MemoryMax=768M","TasksMax=64","CPUQuota=100%",
                      "RuntimeDirectoryMode=0700","actual!=pinned",
                      "production_sandbox_certified"):
            self.assertIn(token,src)
        for forbidden in ("useradd","apt install","systemctl enable","chmod -R 777"):
            self.assertNotIn(forbidden,src)

    def test_real_engine_worker_and_cleanup_proof(self):
        src=SOURCE.read_text()
        self.assertIn("urano.engine_worker_process import run",src)
        self.assertIn('"engine_opened":True',src)
        self.assertIn('"worker_closed":True',src)
        self.assertIn('"home_blocked":home_blocked',src)
        self.assertIn('TemporaryDirectory(prefix="montara-i23-bundle."',src)


if __name__=="__main__":
    unittest.main()
