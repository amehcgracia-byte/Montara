"""I19: trusted broker only; fake broker tests orchestration, NOT OS isolation."""
import tempfile
import unittest
from pathlib import Path

from urano.job_recovery_ledger import BusyOwner, JobRecoveryLedger, StaleJob
from urano.project_catalog import ProjectCatalog, ProjectNotFound
from urano.trusted_job_admission import BrokerUnverified, TrustedJobAdmission


class SyntheticBroker:
    def __init__(self):
        self.calls=[]; self.launch_ok=True; self.stop_ok=True
    def launch_and_verify(self, lease):
        self.calls.append(('launch',lease.owner_id,lease.project_id,lease.generation))
        return self.launch_ok
    def stop_and_verify_empty(self,lease):
        self.calls.append(('stop',lease.owner_id,lease.project_id,lease.generation))
        return self.stop_ok


class AdmissionContracts(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='montara-i19-admission-')
        self.addCleanup(tmp.cleanup)
        base=Path(tmp.name)
        self.catalog=ProjectCatalog(base/'projects.sqlite3')
        self.ledger=JobRecoveryLedger(base/'jobs.sqlite3')
        self.broker=SyntheticBroker()
        self.controller=TrustedJobAdmission(self.catalog,self.ledger,self.broker)
        self.a=self.catalog.create('owner-A','A project')
        self.b=self.catalog.create('owner-B','B project')

    def test_failed_startup_recovery_never_allows_admission(self):
        from unittest.mock import patch
        with patch.object(self.ledger,'recover_after_restart',side_effect=OSError('SQLite unavailable')):
            with self.assertRaises(OSError):
                self.controller.startup_reconcile()
        with self.assertRaises(BrokerUnverified):
            self.controller.admit('owner-A',self.a.id)
        self.assertEqual(self.broker.calls,[])
        self.assertEqual(self.controller.startup_reconcile(),())
        running=self.controller.admit('owner-A',self.a.id)
        self.assertEqual(running.state,'running')

    def test_verified_owner_admits_and_stops_with_real_ledger(self):
        with self.assertRaises(BrokerUnverified):
            self.controller.admit('owner-A',self.a.id)
        self.assertEqual(self.controller.startup_reconcile(),())
        job=self.controller.admit('owner-A',self.a.id)
        self.assertEqual(job.state,'running')
        self.assertEqual(self.ledger.get_trusted(job.job_id).state,'running')
        with self.assertRaises(BusyOwner):self.controller.admit('owner-A',self.a.id)
        self.assertEqual(len([c for c in self.broker.calls if c[0]=='launch']),1)
        self.controller.stop(job)
        self.assertEqual(self.ledger.get_trusted(job.job_id).state,'stopped')
        again=self.controller.admit('owner-A',self.a.id)
        self.assertGreater(again.generation,job.generation)
        with self.assertRaises(StaleJob):self.controller.stop(job)

    def test_other_owner_rejected_before_broker_and_ledger(self):
        self.controller.startup_reconcile()
        with self.assertRaises(ProjectNotFound):
            self.controller.admit('owner-A',self.b.id)
        self.assertEqual(self.broker.calls,[])
        self.assertEqual(self.ledger.recover_after_restart(),())

    def test_failed_launch_verified_cleanup_never_ready(self):
        self.controller.startup_reconcile()
        self.broker.launch_ok=False
        with self.assertRaises(BrokerUnverified):
            self.controller.admit('owner-A',self.a.id)
        self.assertEqual(self.broker.calls[0][0],'launch')
        self.assertEqual(self.broker.calls[1][0],'stop')
        self.assertEqual(self.ledger.get_trusted(next(iter(self._job_ids()))).state,'stopped')

    def _job_ids(self):
        with self.ledger._connect() as db:
            return [r['job_id'] for r in db.execute('SELECT job_id FROM urano_engine_jobs')]

    def test_unverified_cleanup_remains_busy_and_blocks_reuse(self):
        self.controller.startup_reconcile()
        self.broker.launch_ok=False
        self.broker.stop_ok=False
        with self.assertRaises(BrokerUnverified):
            self.controller.admit('owner-A',self.a.id)
        self.assertEqual(self.ledger.get_trusted(self._job_ids()[0]).state,'stopping')
        with self.assertRaises(BusyOwner):
            self.controller.admit('owner-A',self.a.id)

    def test_crash_recovery_fences_old_controller_and_can_cleanup_orphan(self):
        self.controller.startup_reconcile()
        job=self.controller.admit('owner-A',self.a.id)
        second=TrustedJobAdmission(self.catalog,JobRecoveryLedger(self.ledger.db_path),self.broker)
        orphans=second.startup_reconcile()
        self.assertEqual(len(orphans),1)
        with self.assertRaises(BusyOwner):second.admit('owner-A',self.a.id)
        self.broker.stop_ok=False
        with self.assertRaises(BrokerUnverified):second.cleanup_orphan(orphans[0])
        self.assertEqual(second.ledger.get_trusted(job.job_id).state,'stopping')
        restarted=TrustedJobAdmission(self.catalog,JobRecoveryLedger(self.ledger.db_path),self.broker)
        orphan2=restarted.startup_reconcile()[0]
        self.broker.stop_ok=True
        restarted.cleanup_orphan(orphan2)
        new=restarted.admit('owner-A',self.a.id)
        self.assertGreater(new.generation,job.generation)
        with self.assertRaises(StaleJob):restarted.cleanup_orphan(orphan2)

    def test_a_and_b_can_have_independent_jobs(self):
        self.controller.startup_reconcile()
        a=self.controller.admit('owner-A',self.a.id)
        b=self.controller.admit('owner-B',self.b.id)
        self.assertNotEqual(a.job_id,b.job_id)
        self.assertEqual(len([x for x in self.broker.calls if x[0]=='launch']),2)
        self.controller.stop(a); self.controller.stop(b)

if __name__=='__main__':unittest.main()
