"""Cloud-neutral resource profiles: fixed authorized units, variable VM capacities."""
import tempfile
import unittest
from pathlib import Path

from urano.restricted_systemd_broker import (
    WorkerResourceProfile, fixed_launch_properties,
)


UNIT = "montara-i24-job-" + "a" * 32
ENGINE = Path("/opt/montara/bundles/engine-" + "b" * 40)
JM = Path("/opt/montara/bundles/jm-" + "c" * 40)


class FlexibleWorkerResourceTests(unittest.TestCase):
    def test_default_preserves_historical_i26_worker_limits(self):
        props = fixed_launch_properties(UNIT, ENGINE)
        self.assertIn("MemoryMax=768M", props)
        self.assertIn("CPUQuota=100%", props)
        self.assertIn("TasksMax=64", props)
        self.assertIn("DynamicUser=yes", props)
        self.assertEqual(
            len([x for x in props if x.startswith("BindReadOnlyPaths=")]), 1)

    def test_bundles_pin_original_jm_without_changing_engine(self):
        profile = WorkerResourceProfile(
            memory_mb=4096, cpu_percent=400, tasks_max=256)
        props = fixed_launch_properties(
            UNIT, ENGINE, jm_bundle=JM, resources=profile,
            owner_id="google-owner-a")
        self.assertIn("MemoryMax=4096M", props)
        self.assertIn("CPUQuota=400%", props)
        self.assertIn("TasksMax=256", props)
        self.assertIn(
            "BindReadOnlyPaths="+str(ENGINE)+":/opt/montara-engine", props)
        self.assertIn(
            "BindReadOnlyPaths="+str(JM)+":/opt/montara-jm", props)
        self.assertIn("StateDirectoryMode=0700", props)
        self.assertEqual(
            len([x for x in props if x.startswith("StateDirectory=")]), 1)
        self.assertTrue(
            next(x for x in props if x.startswith("StateDirectory="))
            .startswith("StateDirectory=montara-owner-"))
        self.assertIn("PrivateNetwork=yes", props)
        self.assertIn("RuntimeDirectoryMode=0700", props)

    def test_persistent_namespace_stable_across_worker_generations(self):
        from urano.worker_state_policy import owner_state_directory
        a=owner_state_directory("google-owner-a")
        b=owner_state_directory("google-owner-b")
        self.assertNotEqual(a,b)
        self.assertEqual(a,owner_state_directory("google-owner-a"))
        self.assertNotIn("google-owner-a",a)
        with self.assertRaises(ValueError):
            fixed_launch_properties(UNIT,ENGINE,jm_bundle=JM)
        with self.assertRaises(ValueError):
            fixed_launch_properties(UNIT,ENGINE,owner_id="owner-a")

    def test_invalid_or_user_named_runtime_bundles_rejected(self):
        for path in (
            Path("/tmp/jm-"+"f"*40),
            Path("/opt/montara/bundles/jm-main"),
            Path("/opt/montara/bundles/../jm-"+"f"*40),
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                fixed_launch_properties(UNIT, ENGINE, jm_bundle=path,
                                        owner_id="owner-a")
        for args in (
            {"memory_mb": 256}, {"cpu_percent": 0},
            {"cpu_percent": 10000}, {"tasks_max": 2},
            {"memory_mb": True}, {"cpu_percent": "400"},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                WorkerResourceProfile(**args)


if __name__ == "__main__":
    unittest.main()
