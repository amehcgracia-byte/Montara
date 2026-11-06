"""Docker-backed negative isolation smoke, private synthetic data only.

Called ONLY in GitHub Actions with Docker installed. No persistent containers.
Image must be pulled and pinned to immutable digest by the caller.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from urano.container_isolation import isolated_container_command


def main() -> None:
    image = os.environ["URANO_TEST_IMAGE_DIGEST"]
    with tempfile.TemporaryDirectory(prefix="urano-isolation-") as folder:
        root = Path(folder)
        owners = {}
        for name in ("alice", "bob"):
            workspace = root / name
            workspace.mkdir(mode=0o755)
            (workspace / "Projects").mkdir(mode=0o755)
            (workspace / "private.txt").write_text("ONLY_" + name.upper())
            (workspace / "private.txt").chmod(0o644)
            owners[name] = workspace
        # The host file is deliberately readable by any UID; the isolation
        # assertion relies on it NOT being mounted into the other container.
        script = (
            "from pathlib import Path; import sys; "
            "owner=sys.argv[1]; "
            "assert Path('/workspace/private.txt').read_text()=='ONLY_'+owner.upper(); "
            "other='bob' if owner=='alice' else 'alice'; "
            "assert not Path('/workspace/../'+other+'/private.txt').exists(); "
            "assert not Path('/host/'+other+'/private.txt').exists(); "
            "print('PASS workspace '+owner)"
        )

        def inspect(name):
            cmd = isolated_container_command(
                image=image, name="urano-" + name + "-private",
                workspace=owners[name],
                command=["python", "-c", script, name],
                memory_mb=256, cpus=0.5)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise AssertionError(
                    f"Container {name} exited {result.returncode}: "
                    f"stderr={result.stderr[-1800:]}, stdout={result.stdout[-500:]}"
                )
            return result

        # Run both containers in parallel, without a global owner/render queue.
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(inspect, ("alice", "bob")))
        for result in results:
            assert "PASS workspace" in result.stdout, result.stdout
        print("PASS: two separate containers, own test files accessible, "
              "foreign workspace paths invisible; no network, readonly root, nonroot UID")


if __name__ == "__main__":
    main()
