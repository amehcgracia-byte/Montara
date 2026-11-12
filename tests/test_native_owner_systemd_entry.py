"""Supervisor entry contracts without changing the running GCP Owner worker.

The same arguments are passed by the existing operator-controlled broker;
none may be supplied or overridden by a browser or project payload.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from urano.native_owner_systemd_entry import (
    NativeSystemdOwnerError,
    trusted_native_worker_args,
)

UNIT = "montara-i24-job-" + "a" * 32
WORKSPACE = "f3d5c945-2f14-49bf-b074-ff9ba1deacb7"
OWNER = "montara-owner-" + "9" * 40


class NativeSystemdOwnerArgsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="montara-systemd-contract-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / "run"
        self.run.mkdir()
        self.runtime = self.run / UNIT
        self.runtime.mkdir(mode=0o700)
        self.state = self.base / OWNER
        self.state.mkdir(mode=0o700)
        self.argv = [
            "/opt/montara-engine", UNIT, WORKSPACE, "4",
            "--jm-bundle", "/opt/montara-jm",
            "--private-proxy-limit-mib", "2048",
        ]

    def validate(self, argv=None, state=None, runtime=None):
        return trusted_native_worker_args(
            self.argv if argv is None else argv,
            state_directory=str(self.state) if state is None else state,
            runtime_root=self.runtime if runtime is None else runtime,
            runtime_base=self.run,
        )

    def test_exact_operator_invocation_and_existing_broker_ready_identity(self):
        state, runtime, uuid, generation, quota = self.validate()
        self.assertEqual(state, self.state)
        self.assertEqual(runtime, self.runtime)
        self.assertEqual(uuid, WORKSPACE)
        self.assertEqual(generation, 4)
        self.assertEqual(quota, 2048)
        without_optional = self.validate(self.argv[:6])
        self.assertEqual(without_optional[-1], 256)

    def test_untrusted_script_paths_or_worker_ids_are_rejected(self):
        bad = [
            (0, "/tmp/evil-engine"),
            (1, "montara-i24-job-" + "!" * 32),
            (2, "owner-a-draft"),
            (2, "../../other-user"),
            (3, "0"),
            (3, "-1"),
            (3, "abc"),
            (4, "--other-flag"),
            (5, "/opt/foreign-jm"),
            (6, "--exec"),
            (7, "4097"),
            (7, "0"),
        ]
        for position, value in bad:
            with self.subTest(position=position, value=value):
                args = list(self.argv)
                args[position] = value
                with self.assertRaises(NativeSystemdOwnerError):
                    self.validate(args)

    def test_legacy_synthetic_worker_argument_shapes_are_rejected(self):
        for args in ([], self.argv[:3], self.argv[:5],
                     [*self.argv, "--extra", "1"]):
            with self.subTest(args=args):
                with self.assertRaises(NativeSystemdOwnerError):
                    self.validate(args)

    def test_state_directory_must_be_unique_and_private(self):
        for state in ("", str(self.state) + ":" + str(self.state),
                      str(self.base), "/tmp/foreign",
                      "/var/lib/montara-owner-" + "!" * 40):
            with self.subTest(state=state):
                with self.assertRaises(NativeSystemdOwnerError):
                    self.validate(state=state)
        self.state.chmod(0o755)
        with self.assertRaises(NativeSystemdOwnerError):
            self.validate()
        self.state.chmod(0o700)

    def test_linked_state_directory_is_rejected(self):
        link = self.base / ("montara-owner-" + "8" * 40)
        link.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(NativeSystemdOwnerError):
            self.validate(state=str(link))

    def test_runtime_directory_and_permissions_are_fixed_to_unit(self):
        other = self.run / ("montara-i24-job-" + "b" * 32)
        other.mkdir(mode=0o700)
        with self.assertRaises(NativeSystemdOwnerError):
            self.validate(runtime=other)
        self.runtime.chmod(0o777)
        with self.assertRaises(NativeSystemdOwnerError):
            self.validate()
        self.runtime.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
