"""U13D2B contract: hardened per-owner container argv and invalid input guards."""
import tempfile
import unittest
from pathlib import Path

from urano.container_isolation import isolated_container_command


IMAGE = "python@sha256:" + "a" * 64


class ContainerIsolationContract(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.alice = self.root / "alice"
        self.alice.mkdir()
        (self.alice / "Projects").mkdir()
        self.bob = self.root / "bob"
        self.bob.mkdir()
        (self.bob / "Projects").mkdir()

    def command(self, workspace=None, **kwargs):
        args = dict(image=IMAGE, name="urano-alice-0001",
                    workspace=workspace or self.alice,
                    command=["python", "-c", "print(42)"])
        args.update(kwargs)
        return isolated_container_command(**args)

    def test_every_instance_is_without_network_privileges_or_host_root(self):
        cmd = self.command()
        self.assertEqual(cmd[:2], ["docker", "run"])
        for required in ("--read-only", "none", "ALL", "no-new-privileges:true",
                         "--pids-limit", "--memory", "--cpus", "--user"):
            self.assertIn(required, cmd)
        self.assertIn("type=bind,src=" + str(self.alice.resolve()) + ",dst=/workspace,rw", cmd)
        self.assertNotIn(str(self.bob), " ".join(cmd))
        self.assertNotIn("--privileged", cmd)
        self.assertNotIn("/var/run/docker.sock", " ".join(cmd))
        self.assertEqual(cmd[-3:], ["python", "-c", "print(42)"])

    def test_different_owners_never_mount_same_directory(self):
        ac = self.command()
        bc = self.command(workspace=self.bob, name="urano-bob-00002")
        self.assertNotEqual(ac[ac.index("--mount") + 1],
                            bc[bc.index("--mount") + 1])

    def test_invalid_configuration_rejected(self):
        cases = [
            dict(image="python:latest"),
            dict(image="python@sha256:short"),
            dict(name="other"),
            dict(memory_mb=0),
            dict(memory_mb=True),
            dict(cpus=0),
            dict(uid=0),
            dict(command=["/bin/sh", "\x00"]),
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.command(**change)

    def test_symlink_workspace_and_projects_rejected(self):
        link = self.root / "alias"
        link.symlink_to(self.alice, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.command(workspace=link)
        (self.bob / "Projects").rmdir()
        (self.bob / "Projects").symlink_to(self.alice / "Projects", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.command(workspace=self.bob)


if __name__ == "__main__":
    unittest.main()
