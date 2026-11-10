"""I26 synthetic Engine worker under systemd DynamicUser (LAB ONLY).

Retains the actual Flask Engine client in memory until its cgroup is stopped.
No media, public sockets, original files or untrusted filesystem paths.
"""
import json
import os
import re
import signal
import sys
import time
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        raise SystemExit(2)
    bundle = Path(sys.argv[1])
    unit = sys.argv[2]
    if not re.fullmatch(r"montara-i24-job-[0-9a-f]{32}",unit):
        raise SystemExit(3)
    sys.path[:0] = [str(bundle/"site"), str(bundle/"app"), str(bundle/"engine")]
    from core.project import new_project_document
    from urano.engine_worker_process import make_engine_client
    data = Path("/run") / unit
    folder = data / "Projects" / "I26-Synthetic"
    folder.mkdir(parents=True)
    (folder/"project.json").write_text(json.dumps(new_project_document("I26-Synthetic")))
    client = make_engine_client(bundle/"engine", data)
    opened = client.post("/api/v1/wizard/projects/open", json={"path": str(folder)})
    state = client.application.config.get("ZUCKER_STATE")
    loaded = getattr(getattr(state,"project",None),"folder",None)
    inspected = client.get("/api/v1/project")
    if (opened.status_code != 200 or inspected.status_code != 200 or
            not isinstance(loaded,(str,Path)) or Path(loaded).resolve() != folder.resolve()):
        raise RuntimeError("Real Engine did not attest expected opened project")
    tmp = data / "ready.tmp"
    tmp.write_text(json.dumps({"ready":True,"uid":os.getuid(),"folder":"I26-Synthetic"}))
    os.replace(tmp,data/"ready.json")
    signal.signal(signal.SIGTERM,lambda signum,frame:sys.exit(0))
    while True:
        time.sleep(2)


if __name__ == "__main__":
    main()

