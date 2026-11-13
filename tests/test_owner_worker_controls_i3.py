"""I3 Owner worker-security contracts: no systemd or privileged OS actions."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore
from urano.job_recovery_ledger import JobRecoveryLedger, BusyOwner, StaleJob
from urano.private_owner_admission import OwnerAdmissionDenied, verify_owner_and_project
from urano.private_stage_owner_admission import verify_stage_owner_request
from urano.restricted_broker_ipc import parse_stop, stop_authenticated
from urano.restricted_systemd_broker import (
    RestrictedTargetControl, UnverifiedTarget, WorkerResourceProfile,
    expected_cgroup, fixed_launch_properties,
)
from urano.worker_state_policy import owner_state_directory


def request(op, s, project):
    return json.dumps({"op":op,"session":s.token,"csrf":s.csrf,
                       "project_id":project}).encode("ascii")


class WorkerIsolationContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-i3-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.sessions = SessionStore(self.root / "sessions.sqlite3")
        self.catalog = ProjectCatalog(self.root / "projects.sqlite3")
        self.ledger = JobRecoveryLedger(self.root / "jobs.sqlite3")
        self.a = self.sessions.issue("alice")
        self.b = self.sessions.issue("bob")
        self.pa = self.catalog.create("alice", "Stage A")
        self.pb = self.catalog.create("bob", "Stage B")

    def test_real_sqlite_owner_admission_rejects_foreign_project_and_wrong_csrf(self):
        op, owner, project = verify_owner_and_project(
            request("ensure_owner", self.a, self.pa.id), owner_db_root=self.root)
        self.assertEqual((op,owner,project),("ensure_owner","alice",self.pa.id))
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(request("ensure_owner", self.a, self.pb.id),
                                     owner_db_root=self.root)
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(request("ensure_owner", self.b, self.pa.id),
                                     owner_db_root=self.root)
        forged = json.loads(request("ensure_owner", self.a, self.pa.id))
        forged["csrf"] = "a" * 64
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(json.dumps(forged).encode(), owner_db_root=self.root)

    def test_bad_browser_fields_never_select_broker_uid_unit_or_owner(self):
        values = json.loads(request("ensure_owner",self.a,self.pa.id))
        for key, value in (("owner_id", "bob"), ("unit", "montara-any"), ("uid", 0)):
            bad = dict(values, **{key:value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_owner_and_project(json.dumps(bad).encode(),
                                         owner_db_root=self.root)
        with self.assertRaises(ValueError):
            parse_stop(json.dumps({"op":"stop","job_id":"job-"+"a"*32,
                                   "generation":True}).encode())
        with self.assertRaises(ValueError):
            expected_cgroup("montara-i24-job-" + "../etc")

    def test_expired_session_cannot_admit_worker(self):
        old = self.sessions.issue("alice",ttl_seconds=1,now=int(time.time())-9)
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(request("ensure_owner",old,self.pa.id),
                                     owner_db_root=self.root)

    def test_per_owner_lock_crash_fence_and_verified_release(self):
        first = self.ledger.start_trusted("alice",self.pa.id)
        unit = self.ledger.reserve_target_unit(first)
        self.assertEqual(unit,"montara-i24-job-"+first.job_id[4:])
        self.ledger.mark_running(first)
        with self.assertRaises(BusyOwner):
            self.ledger.start_trusted("alice",self.pa.id)
        # A distinct owner remains independent even while Alice is busy.
        other = self.ledger.start_trusted("bob",self.pb.id)
        self.assertNotEqual(first.job_id,other.job_id)
        orphans = self.ledger.recover_after_restart()
        self.assertEqual({x.owner_id for x in orphans},{"alice","bob"})
        with self.assertRaises(BusyOwner):
            self.ledger.start_trusted("alice",self.pa.id)
        with self.assertRaises(ValueError):
            self.ledger.confirm_stopped(orphans[0],verified_cgroup_empty=False)
        alice_orphan = next(x for x in orphans if x.owner_id=="alice")
        stopping = self.ledger.request_stop(alice_orphan)
        self.ledger.confirm_stopped(stopping,verified_cgroup_empty=True)
        latest = self.ledger.start_trusted("alice",self.pa.id)
        self.assertEqual(latest.generation,first.generation+1)
        with self.assertRaises(StaleJob):
            self.ledger.reserve_target_unit(first)

    def test_operator_fixed_systemd_resource_and_state_namespace(self):
        digest_a=owner_state_directory("alice")
        self.assertEqual(digest_a,owner_state_directory("alice"))
        self.assertNotEqual(digest_a,owner_state_directory("bob"))
        unit="montara-i24-job-"+("f"*32)
        engine=Path("/opt/montara/bundles/engine-"+("a"*40))
        jm=Path("/opt/montara/bundles/jm-"+("b"*40))
        props=fixed_launch_properties(unit,engine,jm_bundle=jm,owner_id="alice")
        self.assertIn("DynamicUser=yes",props)
        self.assertIn("PrivateNetwork=yes",props)
        self.assertIn("StateDirectory="+digest_a,props)
        self.assertIn("KillMode=control-group",props)
        self.assertTrue(any(x.startswith("MemoryMax=") for x in props))
        with self.assertRaises(ValueError):
            fixed_launch_properties(unit,Path("/tmp/foreign-engine"),jm_bundle=jm,owner_id="alice")
        with self.assertRaises(ValueError):
            fixed_launch_properties(unit,engine,jm_bundle=jm,owner_id=None)
        with self.assertRaises(ValueError):
            WorkerResourceProfile(memory_mb=0)

    def test_unknown_cgroup_must_not_release_owner_slot(self):
        lease=self.ledger.start_trusted("alice",self.pa.id)
        self.ledger.reserve_target_unit(lease)
        running=self.ledger.mark_running(lease)
        control=RestrictedTargetControl(self.ledger,Mock())
        control.systemd.show.return_value={"ControlGroup":"/system.slice/not-our-unit","ActiveState":"active"}
        with self.assertRaises(UnverifiedTarget):
            control.stop_verified(running)
        control.systemd.stop_exact.assert_not_called()
        self.assertEqual(self.ledger.unverified_for_owner("alice")[0].state,"running")

    def test_stage_snapshot_requires_real_owner_and_matching_generation(self):
        def stage(session, project_id, generation=1):
            return json.dumps({"op":"stage_snapshot_owner",
                               "session":session.token,"csrf":session.csrf,
                               "project_id":project_id,
                               "generation":generation}).encode()
        result=verify_stage_owner_request(stage(self.a,self.pa.id),owner_db_root=self.root)
        self.assertEqual(result,("alice",self.pa.id,1))
        with self.assertRaises(OwnerAdmissionDenied):
            verify_stage_owner_request(stage(self.a,self.pb.id),owner_db_root=self.root)
        with self.assertRaises(OwnerAdmissionDenied):
            verify_stage_owner_request(stage(self.b,self.pa.id),owner_db_root=self.root)
        for generation in (0,True,-1,2**31):
            with self.subTest(generation=generation),self.assertRaises(ValueError):
                verify_stage_owner_request(stage(self.a,self.pa.id,generation),
                                           owner_db_root=self.root)


if __name__=="__main__":
    unittest.main()
