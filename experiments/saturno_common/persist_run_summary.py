"""Persist a compact GitHub Actions result on the research branch.

Use only in an explicitly authorized workflow with contents: write.
The workflow must trigger only on its own YAML path so this push cannot loop.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

BRANCH = "fernando/continuacion-montara"

def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()

def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: persist_run_summary.py EXPERIMENT STATUS_JSON OUT_PATH")
    experiment, source, destination = sys.argv[1:]
    if not experiment.startswith("SATURNO-"):
        raise SystemExit("Unexpected experiment")
    ref = os.getenv("GITHUB_REF", "")
    if ref != f"refs/heads/{BRANCH}":
        raise SystemExit(f"Ref mismatch: {ref}; refusing write")
    run_id = os.getenv("GITHUB_RUN_ID")
    head_sha = os.getenv("GITHUB_SHA")
    if not run_id or not head_sha:
        raise SystemExit("Missing Actions metadata")
    payload = json.loads(Path(source).read_text())
    # Store only compact summary, never frame hash arrays, binary payloads or credentials.
    summary = {
        "experiment": experiment,
        "run_id": run_id,
        "run_url": f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{run_id}",
        "tested_commit": head_sha,
        "status": payload.get("status", "UNKNOWN"),
        "error": payload.get("error"),
        "comparisons": payload.get("comparisons"),
        "segments": {
            k: {
                "requested_frames": v.get("requested_frames"),
                "frame_counts": v.get("frame_counts"),
                "comparisons": v.get("comparisons"),
            } for k, v in payload.get("segments", {}).items()
        },
    }
    target = Path(destination)
    if target.is_absolute() or ".." in target.parts or target.parts[0] != "experiments":
        raise SystemExit("Output path must stay under experiments/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2) + "\n")
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "--", str(target))
    if not git("status", "--porcelain", "--", str(target)):
        print("RESULT_ALREADY_PERSISTED")
        return
    git("commit", "-m", f"docs({experiment.lower()}): persist workflow result [skip ci]", "--", str(target))
    # No force-push. Reject concurrent changes; reconcile manually if rejected.
    git("push", "origin", f"HEAD:refs/heads/{BRANCH}")
    print("PERSISTED_RESULT=" + str(target))

if __name__ == "__main__":
    main()
