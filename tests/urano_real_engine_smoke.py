"""Real Engine U13C smoke: synthetic projects only, subprocess and stdio.

Run in CI with recursive Engine submodule and Montara requirements installed.
No videos, FFmpeg export, private files, cloud workers or persistent user data.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    repo = Path(__file__).resolve().parents[1]
    engine = (repo / "engine").resolve()
    if not (engine / "server" / "api.py").is_file():
        raise RuntimeError("Pinned Engine submodule must be initialized")
    sys.path.insert(0, str(engine))
    from core.project import new_project_document

    with tempfile.TemporaryDirectory(prefix="urano-real-engine-") as tmp:
        root = Path(tmp)
        for name in ("Earlier", "Recent"):
            project_dir = root / "Projects" / name
            project_dir.mkdir(parents=True)
            document = new_project_document(name)
            (project_dir / "project.json").write_text(
                json.dumps(document), encoding="utf-8"
            )
        commands = [
            {"op": "open", "folder": "Earlier"},
            {"op": "open", "folder": "Recent"},
            {"op": "open", "folder": "../untrusted"},
            {"op": "stop"},
        ]
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        worker = subprocess.Popen(
            [sys.executable, "-m", "urano.engine_worker_process",
             "--engine-dir", str(engine), "--data-root", str(root)],
            cwd=str(repo), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            output, errors = worker.communicate(
                "".join(json.dumps(command) + "\n" for command in commands), timeout=90
            )
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.communicate(timeout=10)
            raise AssertionError("Real Engine worker exceeded 90-second smoke deadline")
        if worker.returncode != 0:
            raise AssertionError("Real Engine worker failed: " + errors[-2000:])
        messages = [json.loads(line) for line in output.splitlines()]
        if [message.get("type") for message in messages] != [
            "ready", "opened", "opened", None, "stopped"
        ]:
            raise AssertionError(f"Unexpected worker protocol: {messages!r}")
        if ([messages[1]["folder"], messages[2]["folder"]] !=
            ["Earlier", "Recent"] or messages[3].get("ok") is not False):
            raise AssertionError(f"Failed old/new project or traversal checks: {messages!r}")
        print("PASS: pinned real Engine opened two synthetic projects in its own process; "
              "traversal denied, protocol stopped cleanly.")


if __name__ == "__main__":
    main()
