"""U13E1 ephemeral Docker acceptance, invoked only on GitHub-hosted runners."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from urano.container_isolation import isolated_container_command


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("This script is exclusively for disposable GitHub Actions runners")
    image = os.environ["URANO_TEST_IMAGE_ID"]
    temp = tempfile.TemporaryDirectory(prefix="urano-real-ingest-")
    root = Path(temp.name)
    workspace = root / "media"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    (workspace / "Projects").mkdir(mode=0o777)
    (workspace / "Projects").chmod(0o777)
    try:
        command = isolated_container_command(
            image=image, name="urano-media-ingest-ci", workspace=workspace,
            command=["python", "/app/tests/urano_engine_ingest_in_container.py",
                     "/workspace"],
            memory_mb=2048, cpus=2.0
        )
        # No host media paths other than the disposable synthetic workspace.
        # Code/image remain immutable; network disabled; no Docker socket.
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=300)
        if result.returncode:
            raise AssertionError("Real Engine ingest failed inside Docker: " +
                                 result.stderr[-1600:] + result.stdout[-1000:])
        lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
        assert lines, "No structured ingest report from Engine"
        summary = json.loads(lines[-1])
        assert summary["passed"] and summary["engine_stage"] == "ingest", summary
        assert summary["export_tested"] is False and summary["companion_tested"] is False
        print("PASS: Engine ingest on synthetic camera+master inside private Docker container")
        print(json.dumps(summary, sort_keys=True))
    finally:
        # Only for disposable CI files created by container UID, NEVER host data.
        reclaimed = subprocess.run(
            ["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(root)],
            capture_output=True, text=True, timeout=20)
        if reclaimed.returncode:
            raise AssertionError("Could not reclaim disposable CI project files")
        temp.cleanup()


if __name__ == "__main__":
    main()
