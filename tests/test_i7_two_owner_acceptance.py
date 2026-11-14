"""I7 independent two-owner admission-to-recovery acceptance contract.

Exercises real SQLite, session policy and generation fencing, with no
network, browser, cloud credentials, systemd, or live media.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from urano.project_catalog import ProjectCatalog
from urano.session_auth import SessionStore
from urano.job_recovery_ledger import JobRecoveryLedger, BusyOwner, StaleJob
from urano.private_owner_admission import verify_owner_and_project, OwnerAdmissionDenied
from urano.private_stage_owner_admission import verify_stage_owner_request
from urano.worker_state_policy import owner_state_directory


class TwoOwnerAcceptance(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="montara-i7-two-owner-")
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.sessions=SessionStore(self.root/"sessions.sqlite3")
        self.catalog=ProjectCatalog(self.root/"projects.sqlite3")
        self.ledger=JobRecoveryLedger(self.root/"jobs.sqlite3")
        self.a=self.sessions.issue("owner-a")
        self.b=self.sessions.issue("owner-b")
        self.pa=self.catalog.create("owner-a","Stage A")
        self.pb=self.catalog.create("owner-b","Stage B")

    def packet(self, session, project, *, op="ensure_owner", generation=None, csrf=None):
        obj={"op":op,"session":session.token,
             "csrf":session.csrf if csrf is None else csrf,
             "project_id":project.id}
        if generation is not None:
            obj["generation"]=generation
        return json.dumps(obj, separators=(",",":")).encode()

    def test_both_owners_have_distinct_authorized_projects_and_state(self):
        for owner,session,project in (("owner-a",self.a,self.pa),("owner-b",self.b,self.pb)):
            with self.subTest(owner=owner):
                self.assertEqual(
                    verify_owner_and_project(self.packet(session,project),
                                             owner_db_root=self.root),
                    ("ensure_owner",owner,project.id))
        self.assertNotEqual(owner_state_directory("owner-a"),
                            owner_state_directory("owner-b"))

    def test_cross_owner_access_denied_in_both_directions(self):
        for session,other in ((self.a,self.pb),(self.b,self.pa)):
            with self.subTest(session=session.token[:4]):
                with self.assertRaises(OwnerAdmissionDenied):
                    verify_owner_and_project(self.packet(session,other),
                                             owner_db_root=self.root)
                with self.assertRaises(OwnerAdmissionDenied):
                    verify_stage_owner_request(
                        self.packet(session,other,op="stage_snapshot_owner",generation=1),
                        owner_db_root=self.root)

    def test_wrong_csrf_denied_with_real_store(self):
        with self.assertRaises(OwnerAdmissionDenied):
            verify_owner_and_project(
                self.packet(self.a,self.pa,csrf="0"*64),
                owner_db_root=self.root)

    def test_parallel_reservations_do_not_share_unit_or_generation(self):
        first=self.ledger.start_trusted("owner-a",self.pa.id)
        second=self.ledger.start_trusted("owner-b",self.pb.id)
        ua=self.ledger.reserve_target_unit(first)
        ub=self.ledger.reserve_target_unit(second)
        self.assertNotEqual(ua,ub)
        self.assertEqual(first.generation,1)
        self.assertEqual(second.generation,1)
        self.ledger.mark_running(first)
        self.ledger.mark_running(second)
        with self.assertRaises(BusyOwner):
            self.ledger.start_trusted("owner-a",self.pa.id)
        self.assertEqual(len(self.ledger.unverified_for_owner("owner-b")),1)

    def test_stop_requires_verified_cgroup_without_affecting_second_owner(self):
        first=self.ledger.start_trusted("owner-a",self.pa.id)
        second=self.ledger.start_trusted("owner-b",self.pb.id)
        self.ledger.reserve_target_unit(first)
        self.ledger.reserve_target_unit(second)
        self.ledger.mark_running(first)
        self.ledger.mark_running(second)
        stopping=self.ledger.request_stop(first)
        with self.assertRaises(ValueError):
            self.ledger.confirm_stopped(stopping,verified_cgroup_empty=False)
        with self.assertRaises(BusyOwner):
            self.ledger.start_trusted("owner-a",self.pa.id)
        self.ledger.confirm_stopped(stopping,verified_cgroup_empty=True)
        next_a=self.ledger.start_trusted("owner-a",self.pa.id)
        self.assertEqual(next_a.generation,2)
        self.assertEqual(self.ledger.unverified_for_owner("owner-b")[0].job_id,
                         second.job_id)
        with self.assertRaises(StaleJob):
            self.ledger.mark_running(first)

    def test_restart_fences_both_owners_until_individually_verified(self):
        a=self.ledger.start_trusted("owner-a",self.pa.id)
        b=self.ledger.start_trusted("owner-b",self.pb.id)
        self.ledger.reserve_target_unit(a)
        self.ledger.reserve_target_unit(b)
        self.ledger.mark_running(a)
        self.ledger.mark_running(b)
        restarted=JobRecoveryLedger(self.root/"jobs.sqlite3")
        orphans=restarted.recover_after_restart()
        self.assertEqual({x.owner_id for x in orphans},{"owner-a","owner-b"})
        with self.assertRaises(BusyOwner):
            restarted.start_trusted("owner-a",self.pa.id)
        with self.assertRaises(BusyOwner):
            restarted.start_trusted("owner-b",self.pb.id)
        orphan_a=next(x for x in orphans if x.owner_id=="owner-a")
        restarted.confirm_stopped(
            restarted.request_stop(orphan_a),verified_cgroup_empty=True)
        self.assertEqual(restarted.start_trusted("owner-a",self.pa.id).generation,2)
        with self.assertRaises(BusyOwner):
            restarted.start_trusted("owner-b",self.pb.id)


if __name__=="__main__":
    unittest.main()
