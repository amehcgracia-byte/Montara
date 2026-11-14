"""No real poweroff, broker, systemd or existing live state required."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.owner_poweroff_guard import OwnerPoweroffUnknown, may_poweroff


class I6bReadOnlyOwnerPreflight(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-i6b-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.a = self.root/"a.sqlite3"
        self.b = self.root/"b.sqlite3"
        self.la = JobRecoveryLedger(self.a)
        self.lb = JobRecoveryLedger(self.b)

    def safe(self):
        return may_poweroff(ledger_paths=(self.a,self.b))

    def test_empty_ledgers_are_candidates_only(self):
        self.assertTrue(self.safe())

    def test_another_owner_reservation_blocks_poweroff(self):
        lease = self.la.start_trusted("alice","project-a")
        self.assertFalse(self.safe())
        self.la.reserve_target_unit(lease)
        self.la.mark_running(lease)
        self.assertFalse(self.safe())

    def test_stopping_and_orphaned_never_count_as_idle(self):
        lease=self.la.start_trusted("alice","project-a")
        self.la.reserve_target_unit(lease)
        running=self.la.mark_running(lease)
        stopping=self.la.request_stop(running)
        self.assertFalse(self.safe())
        self.la.recover_after_restart()
        self.assertFalse(self.safe())
        with self.assertRaises(ValueError):
            self.la.confirm_stopped(stopping,verified_cgroup_empty=False)

    def test_verified_cleanup_restores_candidate(self):
        lease=self.la.start_trusted("alice","project-a")
        self.la.reserve_target_unit(lease)
        running=self.la.mark_running(lease)
        self.la.confirm_stopped(
            self.la.request_stop(running),verified_cgroup_empty=True)
        self.assertTrue(self.safe())

    def test_missing_or_corrupt_ledger_fails_closed(self):
        with self.assertRaises(OwnerPoweroffUnknown):
            may_poweroff(ledger_paths=(self.a,self.root/"missing.sqlite3"))
        self.b.write_bytes(b"not a sqlite database")
        with self.assertRaises(OwnerPoweroffUnknown):
            self.safe()

    def test_untrusted_paths_denied(self):
        with self.assertRaises(OwnerPoweroffUnknown):
            may_poweroff(ledger_paths=())
        with self.assertRaises(OwnerPoweroffUnknown):
            may_poweroff(ledger_paths=(Path("relative.sqlite3"),))
        link=self.root/"linked.sqlite3"
        link.symlink_to(self.a)
        with self.assertRaises(OwnerPoweroffUnknown):
            may_poweroff(ledger_paths=(link,))

    def test_concurrent_other_owner_lease_keeps_vm_running(self):
        lease=self.lb.start_trusted("bob","project-b")
        self.assertFalse(self.safe())
        self.lb.reserve_target_unit(lease)
        running=self.lb.mark_running(lease)
        self.lb.confirm_stopped(
            self.lb.request_stop(running),verified_cgroup_empty=True)
        self.assertTrue(self.safe())


if __name__=="__main__":
    unittest.main()
