"""I6c real flock concurrency + real SQLite, without powering off VM."""
from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from urano.job_recovery_ledger import JobRecoveryLedger
from urano.owner_shutdown_barrier import (
    OwnerShutdownBarrier, OwnerShutdownBlocked, guarded_owner_start,
)


class BarrierTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="montara-i6c-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.root.chmod(0o700)
        self.barrier = OwnerShutdownBarrier(self.root)
        self.db = self.root / "ledger.sqlite3"
        self.ledger = JobRecoveryLedger(self.db)

    def test_empty_ledger_arms_draining_only_on_poweroff_request(self):
        called=[]
        self.assertTrue(self.barrier.shutdown_if_idle(
            (self.db,), lambda: called.append("requested")))
        self.assertEqual(called, ["requested"])
        with self.assertRaises(OwnerShutdownBlocked):
            with self.barrier.admit():
                pass
        self.assertTrue((self.root/"draining").is_file())

    def test_reserved_worker_blocks_poweroff_without_marker(self):
        self.ledger.start_trusted("alice","project-a")
        self.assertFalse(self.barrier.shutdown_if_idle(
            (self.db,), lambda: self.fail("must not poweroff")))
        self.assertFalse((self.root/"draining").exists())
        with self.barrier.admit():
            pass

    def test_failed_poweroff_request_restores_admission(self):
        def fail():
            raise RuntimeError("systemctl refused")
        with self.assertRaisesRegex(RuntimeError,"refused"):
            self.barrier.shutdown_if_idle((self.db,),fail)
        with self.barrier.admit():
            pass

    def test_exclusive_shutdown_waits_for_inflight_admission(self):
        entered = threading.Event()
        release = threading.Event()
        requested = threading.Event()
        errors=[]
        def start():
            try:
                with self.barrier.admit():
                    entered.set()
                    if not release.wait(timeout=3):
                        raise AssertionError("admission did not finish")
            except BaseException as exc:
                errors.append(exc)
        def shutdown():
            try:
                self.barrier.shutdown_if_idle((self.db,),requested.set)
            except BaseException as exc:
                errors.append(exc)
        a=threading.Thread(target=start)
        a.start()
        self.assertTrue(entered.wait(timeout=2))
        b=threading.Thread(target=shutdown)
        b.start()
        try:
            self.assertFalse(requested.wait(timeout=0.2))
        finally:
            release.set()
            a.join(timeout=3)
            b.join(timeout=3)
        self.assertFalse(a.is_alive() or b.is_alive())
        self.assertEqual(errors,[])
        self.assertTrue(requested.is_set())

    def test_unknown_ledger_never_requests_poweroff(self):
        with self.assertRaises(Exception):
            self.barrier.shutdown_if_idle(
                (self.root/"no-db",),lambda: self.fail("unsafe"))

    def test_nonprivate_directory_or_symlink_denied(self):
        self.root.chmod(0o755)
        with self.assertRaises(OwnerShutdownBlocked):
            OwnerShutdownBarrier(self.root)
        self.root.chmod(0o700)
        link=self.root.parent/(self.root.name+"-link")
        link.symlink_to(self.root)
        self.addCleanup(link.unlink)
        with self.assertRaises(OwnerShutdownBlocked):
            OwnerShutdownBarrier(link)

    def test_decorator_only_enabled_by_operator(self):
        events=[]
        @guarded_owner_start
        def start():
            events.append("started")
        with patch.dict(os.environ,{"MONTARA_OWNER_SHUTDOWN_GATE":"0"}):
            start()
        self.assertEqual(events,["started"])
        with patch.dict(os.environ,{"MONTARA_OWNER_SHUTDOWN_GATE":"1"}),patch(
            "urano.owner_shutdown_barrier.ROOT",self.root):
            # Default argument was bound to root at definition time: patch
            # class constructor instead, using a new temporary barrier.
            with patch("urano.owner_shutdown_barrier.OwnerShutdownBarrier",
                       return_value=self.barrier):
                start()
                (self.root/"draining").touch()
                with self.assertRaises(OwnerShutdownBlocked):
                    start()
        self.assertEqual(events,["started","started"])


if __name__=="__main__":
    unittest.main()
