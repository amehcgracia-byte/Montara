"""I24 durable host unit mapping: never trust browser-supplied unit strings."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from urano.job_recovery_ledger import JobRecoveryLedger, StaleJob


class DurableUnitContracts(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="montara-i24-ledger-")
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/"jobs.sqlite3"
        self.ledger=JobRecoveryLedger(self.path)

    def test_target_reserved_persists_across_restart(self):
        lease=self.ledger.start_trusted("owner-a","project-a")
        name=self.ledger.reserve_target_unit(lease)
        self.assertRegex(name,r"^montara-i24-job-[0-9a-f]{32}$")
        new_ledger=JobRecoveryLedger(self.path)
        self.assertEqual(new_ledger.target_for_trusted(lease),name)
        orphan=new_ledger.recover_after_restart()[0]
        self.assertEqual(new_ledger.target_for_trusted(orphan),name)
        with self.assertRaises(StaleJob):
            new_ledger.reserve_target_unit(lease)

    def test_foreign_or_stale_lease_cannot_claim_target(self):
        lease=self.ledger.start_trusted("owner-a","project-a")
        impostors=(
            lease.__class__("owner-b",lease.project_id,lease.job_id,lease.generation,lease.state),
            lease.__class__(lease.owner_id,"project-b",lease.job_id,lease.generation,lease.state),
            lease.__class__(lease.owner_id,lease.project_id,lease.job_id,lease.generation+1,lease.state),
        )
        for bad in impostors:
            with self.subTest(bad=bad), self.assertRaises(StaleJob):
                self.ledger.reserve_target_unit(bad)
            with self.subTest(bad=bad), self.assertRaises(StaleJob):
                self.ledger.target_for_trusted(bad)

    def test_reject_invalid_unit_source(self):
        lease=self.ledger.start_trusted("owner-a","project-a")
        wrong=lease.__class__(lease.owner_id,lease.project_id,"/system.slice/owner.service",
                              lease.generation,lease.state)
        with self.assertRaises(ValueError):
            self.ledger.reserve_target_unit(wrong)

    def test_migrate_existing_i18_database(self):
        # Simulate the original I18 schema without the unit identity column.
        with sqlite3.connect(self.path) as db:
            db.execute("DROP INDEX IF EXISTS urano_unique_target_unit")
            db.execute("ALTER TABLE urano_engine_jobs DROP COLUMN target_unit")
        again=JobRecoveryLedger(self.path)
        fields={x[1] for x in again._connect().execute("PRAGMA table_info(urano_engine_jobs)")}
        self.assertIn("target_unit",fields)
        lease=again.start_trusted("owner-a","project-a")
        self.assertTrue(again.reserve_target_unit(lease))

    def test_old_generation_cannot_modify_replacement_target(self):
        first=self.ledger.start_trusted("owner-a","project-a")
        self.ledger.reserve_target_unit(first)
        self.ledger.confirm_stopped(self.ledger.request_stop(first),verified_cgroup_empty=True)
        second=self.ledger.start_trusted("owner-a","project-a")
        target=self.ledger.reserve_target_unit(second)
        with self.assertRaises(StaleJob):
            self.ledger.reserve_target_unit(first)
        self.assertEqual(self.ledger.target_for_trusted(second),target)


if __name__=="__main__": unittest.main()

