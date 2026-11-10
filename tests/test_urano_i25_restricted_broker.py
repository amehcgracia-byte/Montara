"""I25: a foreign or stale lease must not operate any systemd service."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from urano.job_recovery_ledger import JobRecoveryLedger, StaleJob
from urano.restricted_systemd_broker import (
    RestrictedTargetControl, UnverifiedTarget, expected_cgroup,
    fixed_launch_properties, target_name_for,
)


class FakeSystemd:
    def __init__(self):
        self.calls=[]
        self.group=None
        self.pids=[]
        self.state="active"
    def show(self,unit):
        self.calls.append(("show",unit))
        return {"ControlGroup":self.group or expected_cgroup(unit),
                "ActiveState":self.state}
    def stop_exact(self,unit):
        self.calls.append(("stop",unit))
        self.state="inactive"


class I25PolicyTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-i25-")
        self.addCleanup(temp.cleanup)
        self.db=JobRecoveryLedger(Path(temp.name)/"ledger.sqlite3")
        self.os=FakeSystemd()
        self.policy=RestrictedTargetControl(self.db,self.os)
        self.job=self.db.start_trusted("owner-A","project-A")
        self.unit=self.db.reserve_target_unit(self.job)

    def test_can_only_resolve_exact_committed_target(self):
        self.assertEqual(self.policy.resolve(self.job).unit_name,self.unit)
        self.assertEqual(self.os.calls,[])

    def test_stale_or_foreign_never_touches_systemd(self):
        for bad in (
            self.job.__class__("owner-B",self.job.project_id,self.job.job_id,self.job.generation,self.job.state),
            self.job.__class__(self.job.owner_id,"project-B",self.job.job_id,self.job.generation,self.job.state),
            self.job.__class__(self.job.owner_id,self.job.project_id,self.job.job_id,self.job.generation+1,self.job.state),
            self.job.__class__(self.job.owner_id,self.job.project_id,"job-"+("f"*32),self.job.generation,self.job.state),
        ):
            with self.subTest(bad=bad),self.assertRaises((StaleJob,UnverifiedTarget)):
                self.policy.stop_verified(bad)
        self.assertEqual(self.os.calls,[])

    def test_stopped_job_cannot_trigger_new_systemd_action(self):
        stopped=self.db.confirm_stopped(
            self.db.request_stop(self.job),verified_cgroup_empty=True)
        with self.assertRaises(StaleJob):
            self.policy.stop_verified(stopped)
        self.assertEqual(self.os.calls,[])

    def test_no_undeclared_service_and_foreign_service_rejected(self):
        wrong=self.db.start_trusted("owner-B","project-B")
        with self.assertRaises(UnverifiedTarget):
            self.policy.stop_verified(wrong)
        self.assertEqual(self.os.calls,[])
        for val in ("/system.slice/other.service","montara-owner-beta","montara-i24-job-other",
                    "montara-i24-job-"+("A"*32),"montara-i24-job-"+("a"*32)+".service"):
            with self.subTest(val=val),self.assertRaises(ValueError):
                expected_cgroup(val)

    def test_tampered_unit_never_stop(self):
        self.os.group="/system.slice/montara-owner-beta.service"
        with self.assertRaises(UnverifiedTarget):
            self.policy.stop_verified(self.job)
        self.assertEqual(self.os.calls,[("show",self.unit)])

    def test_attested_cgroup_empty_only_after_stop(self):
        self.os.group=expected_cgroup(self.unit)
        with patch("pathlib.Path.read_text",side_effect=FileNotFoundError):
            self.assertTrue(self.policy.stop_verified(self.job))
        self.assertEqual([x[0] for x in self.os.calls],["show","stop","show"])

    def test_live_cgroup_pids_deny_cleanup(self):
        self.os.group=expected_cgroup(self.unit)
        with patch("pathlib.Path.read_text",return_value="281\n"):
            self.assertFalse(self.policy.stop_verified(self.job))

    def test_bundle_arguments_fixed_and_version_pinned(self):
        ok=Path("/opt/montara/bundles/engine-"+("f"*40))
        flags=fixed_launch_properties(self.unit,ok)
        self.assertIn("DynamicUser=yes",flags)
        self.assertIn("ProtectHome=yes",flags)
        self.assertIn("PrivateNetwork=yes",flags)
        self.assertIn("RuntimeDirectory="+self.unit,flags)
        for path in (
            Path("/home/user/foo"),Path("/tmp/engine-"+"f"*40),
            Path("/opt/montara/bundles/foo"),Path("/opt/montara/bundles/../evil"),
        ):
            with self.subTest(path=path),self.assertRaises(ValueError):
                fixed_launch_properties(self.unit,path)


if __name__=="__main__":
    unittest.main()

