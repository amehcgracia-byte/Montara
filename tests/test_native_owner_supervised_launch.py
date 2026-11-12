"""Check the exact broker systemd-run command without launching systemd.

Uses the REAL reviewed broker command constructor, ledger and resource policy,
but substitutes the privileged command and kernel ready marker. No user jobs
or host services are touched. A browser cannot choose any of these arguments.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.native_owner_broker_policy import (
    NATIVE_CHEMA_WORKER, SMART_PILOT_WORKER)
from urano.private_broker_service import DemoBroker
from urano.restricted_systemd_broker import (
    WorkerResourceProfile, expected_cgroup,
)

WORKSPACE = "e3153f8c-b4d5-47c2-9bf3-129deed27535"


class NativeOwnerSupervisedLaunchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="montara-broker-run-")
        self.addCleanup(temporary.cleanup)
        self.ledger = JobRecoveryLedger(Path(temporary.name) / "jobs.sqlite3")
        self.broker = DemoBroker.__new__(DemoBroker)
        self.broker.ledger = self.ledger
        self.broker.bundle = Path("/opt/montara/bundles/engine-" + "a" * 40)
        self.broker.jm_bundle = Path("/opt/montara/bundles/jm-" + "b" * 40)
        self.broker.private_preview_limit_mib = 2048
        self.broker.resources = WorkerResourceProfile(
            memory_mb=4096, cpu_percent=250, tasks_max=256)
        self.broker.worker_script = NATIVE_CHEMA_WORKER
        self.calls = []
        self.last_unit = None

        def systemd_show(unit):
            return {
                "ActiveState": "active",
                "ControlGroup": expected_cgroup(unit),
                "MainPID": "25000",
                "MemoryMax": str(self.broker.resources.memory_mb * 1048576),
                "TasksMax": str(self.broker.resources.tasks_max),
            }

        self.broker.control = SimpleNamespace(
            systemd=SimpleNamespace(show=systemd_show),
            stop_verified=lambda lease: False)

    def record_systemd_command(self, args, timeout=12):
        # The actual systemd-run executable is NEVER invoked by this test.
        self.assertEqual(args[0], "/usr/bin/systemd-run")
        self.calls.append(args)
        for item in args:
            if item.startswith("--unit="):
                self.last_unit = item.split("=", 1)[1]
        return subprocess.CompletedProcess(args, 0, "", "")

    def fake_ready(self, encoding=None):
        if self.name != "ready.json":
            raise AssertionError("Unexpected host file read")
        return json.dumps({
            "ready": True, "uid": os.getuid() + 30000,
            "folder": WORKSPACE,
        })

    def test_operator_native_worker_uses_existing_broker_abi_and_limits(self):
        with patch("urano.private_broker_service.cmd",
                   side_effect=self.record_systemd_command), patch(
                   "urano.private_broker_service.Path.read_text",
                   new=self.fake_ready):
            started = self.broker.demo_start("owner-a", WORKSPACE)

        self.assertTrue(started["ok"])
        self.assertEqual(started["generation"], 1)
        self.assertEqual(len(self.calls), 1)
        cmd = self.calls[0]
        self.assertIn("-u", cmd)
        position = cmd.index("-u")
        self.assertEqual(cmd[position + 1], NATIVE_CHEMA_WORKER)
        worker_args = cmd[position + 2:]
        self.assertEqual(worker_args, [
            "/opt/montara-engine", self.last_unit, WORKSPACE, "1",
            "--jm-bundle", "/opt/montara-jm",
            "--private-proxy-limit-mib", "2048",
        ])
        for prop in (
            "DynamicUser=yes", "NoNewPrivileges=yes", "PrivateNetwork=yes",
            "ProtectSystem=strict", "PrivateDevices=yes",
            "StateDirectoryMode=0700", "CPUQuota=250%",
            "MemoryMax=4096M", "TasksMax=256",
        ):
            with self.subTest(prop=prop):
                self.assertIn(prop, cmd)
        self.assertTrue(any(
            value.startswith("BindReadOnlyPaths=") and
            value.endswith(":/opt/montara-jm") for value in cmd))
        self.assertTrue(any(
            value.startswith("StateDirectory=montara-owner-") for value in cmd))
        self.assertEqual(
            self.ledger.get_trusted(started["job_id"]).state, "running")
        self.assertNotIn("owner-a", " ".join(worker_args))
        self.assertNotIn("user-home", " ".join(cmd))

    def test_current_smart_beta_worker_remains_a_separate_allowed_runner(self):
        self.broker.worker_script = SMART_PILOT_WORKER
        with patch("urano.private_broker_service.cmd",
                   side_effect=self.record_systemd_command), patch(
                   "urano.private_broker_service.Path.read_text",
                   new=self.fake_ready):
            self.broker.demo_start("owner-a",WORKSPACE)
        cmd = self.calls[0]
        self.assertEqual(cmd[cmd.index("-u") + 1], SMART_PILOT_WORKER)


if __name__ == "__main__":
    unittest.main()
