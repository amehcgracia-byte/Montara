"""Operator-only broker switch: existing beta remains default, native is opt-in."""
from __future__ import annotations

import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from urano.native_owner_broker_policy import (
    LEGACY_WORKER, SMART_PILOT_WORKER, NATIVE_CHEMA_WORKER,
    trusted_operator_worker_script,
)


class NativeOwnerBrokerPolicyTests(unittest.TestCase):
    def protected_script(self, *, uid=0, mode=stat.S_IFREG | 0o644,
                         symlink=False, exists=True):
        return (
            patch("urano.native_owner_broker_policy.Path.is_symlink",
                  return_value=symlink),
            patch("urano.native_owner_broker_policy.Path.is_file",
                  return_value=exists),
            patch("urano.native_owner_broker_policy.Path.stat",
                  return_value=SimpleNamespace(st_uid=uid, st_mode=mode)),
        )

    def policy(self, script, *, pinned=True, **opts):
        a,b,c=self.protected_script(**opts)
        with a,b,c:
            return trusted_operator_worker_script(
                script, jm_bundle=Path("/opt/reviewed-jm") if pinned else None)

    def test_existing_default_and_smart_beta_worker_are_unchanged(self):
        self.assertEqual(self.policy(None,pinned=False),LEGACY_WORKER)
        self.assertEqual(self.policy(LEGACY_WORKER),LEGACY_WORKER)
        self.assertEqual(self.policy(SMART_PILOT_WORKER),SMART_PILOT_WORKER)

    def test_native_worker_is_only_available_with_operator_jm_bundle(self):
        self.assertEqual(self.policy(NATIVE_CHEMA_WORKER),
                         NATIVE_CHEMA_WORKER)
        with self.assertRaises(ValueError):
            self.policy(NATIVE_CHEMA_WORKER,pinned=False)

    def test_browser_cannot_select_arbitrary_runner(self):
        for bad in ("/bin/sh","/tmp/other-worker.py","../native.py","",
                    "native","/opt/montara/broker-smart-candidate/../other.py",
                    42,None if False else "/opt/montara/broker-smart-candidate/x.py"):
            with self.subTest(candidate=bad):
                with self.assertRaises(ValueError):
                    self.policy(bad)

    def test_symlink_unowned_writable_or_missing_script_is_rejected(self):
        for opts in (
            {"symlink":True},
            {"uid":1000},
            {"mode":stat.S_IFREG|0o666},
            {"mode":stat.S_IFDIR|0o755},
            {"exists":False},
        ):
            with self.subTest(opts=opts):
                with self.assertRaises(ValueError):
                    self.policy(NATIVE_CHEMA_WORKER,**opts)


if __name__=="__main__":
    unittest.main()
