"""H4 Native Owner broker is not allowed to reuse I26 sockets/SQLite.

This is a narrow policy test. The full real worker still requires the
separate root-only systemd service and an acceptance test on GCP.
"""
import unittest
from pathlib import Path

from urano.private_broker_service import (
    operator_broker_namespace, SOCKET, OWNER_SOCKET, LEDGER,
    H4_SOCKET, H4_OWNER_SOCKET, H4_LEDGER,
)
from urano.native_owner_broker_policy import (
    H4_NATIVE_WORKER, SMART_PILOT_WORKER
)

class IsolatedNativeBrokerNamespaceTests(unittest.TestCase):
    def test_existing_beta_defaults_unchanged(self):
        self.assertEqual(
            operator_broker_namespace(
                isolated_h4=False, owner_db_root="/run/montara-i27-owner-ro",
                worker_script=SMART_PILOT_WORKER,jm_bundle="/opt/pin"),
            (SOCKET,OWNER_SOCKET,LEDGER))

    def test_h4_has_three_disjoint_paths(self):
        actual=operator_broker_namespace(
            isolated_h4=True,owner_db_root="/run/montara-h4-owner-ro",
            worker_script=H4_NATIVE_WORKER,jm_bundle="/opt/pin")
        self.assertEqual(actual,(H4_SOCKET,H4_OWNER_SOCKET,H4_LEDGER))
        self.assertTrue(all(isinstance(x,Path) for x in actual))
        self.assertFalse(set(actual) & {SOCKET,OWNER_SOCKET,LEDGER})
        self.assertTrue(all(x.is_absolute() for x in actual))

    def test_h4_cannot_mistake_old_sqlite_or_old_worker(self):
        for root,worker,bundle in (
            ("/run/montara-i27-owner-ro",H4_NATIVE_WORKER,"/opt/pin"),
            ("/run/montara-h4-owner-ro",SMART_PILOT_WORKER,"/opt/pin"),
            ("/run/montara-h4-owner-ro",H4_NATIVE_WORKER,None),
            ("/var/lib/montara-i26-broker",H4_NATIVE_WORKER,"/opt/pin"),
        ):
            with self.subTest(root=root,worker=worker):
                with self.assertRaises(ValueError):
                    operator_broker_namespace(
                        isolated_h4=True,owner_db_root=root,
                        worker_script=worker,jm_bundle=bundle)

    def test_browser_cannot_select_runtime_mode(self):
        for bad in ("true","false",1,0,None,{},[]):
            with self.subTest(mode=bad):
                with self.assertRaises(ValueError):
                    operator_broker_namespace(
                        isolated_h4=bad,owner_db_root="/run/montara-h4-owner-ro",
                        worker_script=H4_NATIVE_WORKER,jm_bundle="/opt/pin")

if __name__=="__main__":
    unittest.main()
