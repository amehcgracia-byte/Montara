"""I26 synthetic Engine worker under systemd DynamicUser (LAB ONLY).

Retains the actual Flask Engine client in memory until its cgroup is stopped.
No media, public sockets, original files or untrusted filesystem paths.
"""
import json
import re
import os
import re
import signal
import sys
import time
from pathlib import Path


def main():
    if len(sys.argv) not in (3,4,5,7):
        raise SystemExit(2)
    jm = None
    if len(sys.argv) == 7:
        if sys.argv[5:] != ["--jm-bundle", "/opt/montara-jm"]:
            raise SystemExit(6)
        jm = Path("/opt/montara-jm")
    bundle = Path(sys.argv[1])
    unit = sys.argv[2]
    if not re.fullmatch(r"montara-i24-job-[0-9a-f]{32}",unit):
        raise SystemExit(3)
    sys.path[:0] = [str(bundle/"site"), str(bundle/"app"), str(bundle/"engine")]
    from core.project import new_project_document
    from urano.engine_worker_process import make_engine_client
    from urano.private_stage_payload import private_stage_snapshot
    from urano.private_stage_unix_transport import serve_stage_socket
    data = Path("/run") / unit
    project_id = sys.argv[3] if len(sys.argv)>=4 else "I26-Synthetic"
    generation = int(sys.argv[4]) if len(sys.argv)>=5 else None
    if (generation is not None and (generation < 1 or project_id == "I26-Synthetic")):
        raise SystemExit(5)
    if (project_id != "I26-Synthetic" and
        not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",project_id)):
        raise SystemExit(4)
    folder = data / "Projects" / project_id
    if folder.is_symlink():
        raise ValueError("Linked project folder denied")
    folder.mkdir(parents=True,exist_ok=True)
    project_file=folder/"project.json"
    if project_file.is_symlink():
        raise ValueError("Linked project metadata denied")
    if not project_file.exists():
        project_file.write_text(json.dumps(new_project_document(project_id)))

    def announce_ready():
        tmp = data / "ready.tmp"
        tmp.write_text(json.dumps({"ready":True,"uid":os.getuid(),"folder":project_id}))
        os.replace(tmp,data/"ready.json")

    signal.signal(signal.SIGTERM,lambda signum,frame:sys.exit(0))
    if jm is not None:
        if generation is None:
            raise ValueError("Full JM worker needs durable generation")
        from urano.full_jm_worker import serve_original_jm_worker
        serve_original_jm_worker(
            engine_root=bundle, jm_root=jm, data_root=data,
            project_id=project_id, generation=generation,
            on_ready=announce_ready,
        )
        return

    # Original I26 Engine-only laboratory remains a separate unchanged mode.
    client = make_engine_client(bundle/"engine", data)
    opened = client.post("/api/v1/wizard/projects/open", json={"path": str(folder)})
    state = client.application.config.get("ZUCKER_STATE")
    loaded = getattr(getattr(state,"project",None),"folder",None)
    inspected = client.get("/api/v1/project")
    if (opened.status_code != 200 or inspected.status_code != 200 or
            not isinstance(loaded,(str,Path)) or Path(loaded).resolve() != folder.resolve()):
        raise RuntimeError("Real Engine did not attest expected opened project")
    if generation is not None:
        # Private local IPC only for an explicitly generation-pinned Owner job.
        # Do not announce readiness until the local socket is actually bound.
        serve_stage_socket(
            data, project_id=project_id, generation=generation,
            read_snapshot=lambda: private_stage_snapshot(client, folder),
            trusted_broker_uid=0, on_listening=announce_ready,
        )
    else:
        announce_ready()
        while True:
            time.sleep(2)


if __name__ == "__main__":
    main()

