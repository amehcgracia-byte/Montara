import tempfile
import threading
import unittest
from pathlib import Path

from urano.job_recovery_ledger import BusyOwner, JobRecoveryLedger, StaleJob


class RecoveryLedgerContract(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='urano-i18-ledger-')
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'jobs.sqlite3'
        self.store=JobRecoveryLedger(self.path)

    def test_normal_process_lifecycle_and_generation_fencing(self):
        a=self.store.start_trusted('owner-A','project-1')
        with self.assertRaises(BusyOwner):self.store.start_trusted('owner-A','project-2')
        running=self.store.mark_running(a)
        with self.assertRaises(StaleJob):self.store.mark_running(a)
        stopping=self.store.request_stop(running)
        with self.assertRaises(ValueError):self.store.confirm_stopped(stopping,verified_cgroup_empty=False)
        with self.assertRaises(BusyOwner):self.store.start_trusted('owner-A','project-2')
        stopped=self.store.confirm_stopped(stopping,verified_cgroup_empty=True)
        self.assertEqual(stopped.state,'stopped')
        next_job=self.store.start_trusted('owner-A','project-2')
        self.assertGreater(next_job.generation,a.generation)
        self.assertNotEqual(next_job.job_id,a.job_id)
        with self.assertRaises(StaleJob):self.store.request_stop(a)

    def test_orphaned_state_prevents_reuse_until_independent_cleanup(self):
        a=self.store.start_trusted('owner-A','project-1')
        b=self.store.start_trusted('owner-B','project-1')
        self.store.mark_running(a)
        restarted=JobRecoveryLedger(self.path)
        orphans=restarted.recover_after_restart()
        self.assertEqual({x.job_id for x in orphans},{a.job_id,b.job_id})
        with self.assertRaises(BusyOwner):restarted.start_trusted('owner-A','project-2')
        with self.assertRaises(BusyOwner):restarted.start_trusted('owner-B','project-2')
        with self.assertRaises(ValueError):restarted.confirm_stopped(orphans[0],verified_cgroup_empty=False)
        for orphan in orphans:
            restarted.confirm_stopped(orphan,verified_cgroup_empty=True)
        self.assertEqual(restarted.recover_after_restart(),())
        self.assertEqual(restarted.start_trusted('owner-A','new').generation,2)

    def test_stale_controller_cannot_modify_later_generation(self):
        first=self.store.start_trusted('alpha','first')
        stopping=self.store.request_stop(first)
        self.store.confirm_stopped(stopping,verified_cgroup_empty=True)
        second=self.store.start_trusted('alpha','second')
        with self.assertRaises(StaleJob):self.store.confirm_stopped(stopping,verified_cgroup_empty=True)
        self.assertEqual(self.store.get_trusted(second.job_id).state,'starting')
        with self.assertRaises(StaleJob):self.store.mark_running(first)

    def test_cross_owner_and_project_spoof_do_not_change_job(self):
        a=self.store.start_trusted('owner-A','project-a')
        for fake in (a.__class__('owner-B',a.project_id,a.job_id,a.generation,a.state),
                     a.__class__(a.owner_id,'project-b',a.job_id,a.generation,a.state),
                     a.__class__(a.owner_id,a.project_id,a.job_id,a.generation+1,a.state)):
            with self.assertRaises(StaleJob):self.store.mark_running(fake)
        self.assertEqual(self.store.get_trusted(a.job_id).state,'starting')

    def test_two_parallel_requests_are_serialized_by_sqlite(self):
        barrier=threading.Barrier(2)
        def run(_):
            barrier.wait(timeout=3)
            try:return self.store.start_trusted('owner-A','one')
            except BusyOwner:return 'busy'
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(run,range(2)))
        self.assertEqual(sum(x=='busy' for x in outcomes),1)
        self.assertEqual(sum(x!='busy' for x in outcomes),1)

    def test_no_ttl_auto_release_and_not_exposed_on_http(self):
        first=self.store.start_trusted('owner-A','project-1')
        self.assertEqual(self.store.recover_after_restart()[0].job_id,first.job_id)
        with self.assertRaises(BusyOwner):self.store.start_trusted('owner-A','new')
        src=(Path(__file__).resolve().parents[1]/'urano/job_recovery_ledger.py').read_text()
        self.assertNotIn('Blueprint(',src)
        self.assertNotIn('app.route(',src)
        self.assertNotIn('subprocess.',src)

if __name__=='__main__':unittest.main()
