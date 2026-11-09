"""C7 deployment gate must not mistake a reachable VM for approved beta."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from urano.c7_deployment_readiness import check_c7_deployment, inspect_host_readonly

BASE = {
    "docker_cli": True,
    "docker_daemon_access": True,
    "isolated_owner_volumes": True,
    "host_loopback_only": True,
    "trusted_https_proxy": True,
    "pinned_https_origin": True,
    "real_google_oauth_configured": True,
    "private_key_material": True,
    "per_owner_workers": True,
    "separate_existing_services": True,
    "operator_approval": True,
    "collaborator_approval": True,
    "engine_image_pinned": True,
}


class C7BetaReadiness(unittest.TestCase):
    def test_complete_explicit_review_can_pass(self):
        state = check_c7_deployment(**BASE)
        self.assertTrue(state.ready_for_private_beta)
        self.assertEqual(len(state.gates), len(BASE))
        self.assertEqual([g.name for g in state.gates], list(dict.fromkeys(g.name for g in state.gates)))
        report = state.public_report()
        self.assertTrue(report["ready_for_private_beta"])
        self.assertEqual(len(report["gates"]), len(BASE))

    def test_every_missing_gate_blocks_beta(self):
        for key in BASE:
            with self.subTest(gate=key):
                result = check_c7_deployment(**{**BASE, key: False})
                self.assertFalse(result.ready_for_private_beta)
                self.assertEqual(sum(not gate.ok for gate in result.gates), 1)

    def test_working_vm_without_docker_or_approvals_is_not_ready(self):
        snapshot = {**BASE,
                    "docker_cli": False,
                    "docker_daemon_access": False,
                    "trusted_https_proxy": False,
                    "operator_approval": False,
                    "collaborator_approval": False}
        report = check_c7_deployment(**snapshot)
        self.assertFalse(report.ready_for_private_beta)
        self.assertEqual({g.name for g in report.gates if not g.ok},
                         {"docker_runtime", "trusted_https_reverse_proxy",
                          "operator_authorization", "collaborator_authorization"})

    def test_host_inventory_never_claims_readiness_from_docker_cli(self):
        with patch("urano.c7_deployment_readiness.shutil.which",
                   side_effect=lambda name: f"/usr/bin/{name}" if name == "docker" else None):
            with patch("urano.c7_deployment_readiness.subprocess.run") as run:
                run.return_value.returncode = 0
                snapshot = inspect_host_readonly()
        self.assertTrue(snapshot["docker_cli"])
        self.assertTrue(snapshot["docker_daemon_access"])
        self.assertFalse(snapshot["ready_for_private_beta"])
        self.assertTrue(snapshot["operator_approval_not_inferred"])

    def test_readonly_inventory_does_not_call_docker_when_not_installed(self):
        with patch("urano.c7_deployment_readiness.shutil.which", return_value=None):
            with patch("urano.c7_deployment_readiness.subprocess.run") as run:
                state = inspect_host_readonly()
                run.assert_not_called()
        self.assertFalse(state["docker_daemon_access"])
        self.assertFalse(state["ready_for_private_beta"])

    def test_public_report_does_not_expose_credentials_or_filesystem_paths(self):
        payload = json.dumps(check_c7_deployment(**BASE).public_report())
        self.assertNotIn("secret", payload.lower())
        self.assertNotIn("/home/", payload)
        self.assertNotIn("token", payload.lower())


if __name__ == "__main__":
    unittest.main()
