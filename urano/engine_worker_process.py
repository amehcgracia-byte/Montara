"""Private JSON-line worker for one isolated URANO Engine process.

Not an HTTP service, not a security sandbox. Run only inside a separately
isolated OS account/container with dedicated data root and no host secrets.
The parent must resolve owner/project via U13A and reserve via U13B first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import re
import hashlib
from pathlib import Path


def _project_folder(root: Path, name: str) -> Path:
    # No path traversal, symlinks or arbitrary client-supplied absolute paths.
    from urano.engine_bindings import _FOLDER
    if (not isinstance(name, str) or not _FOLDER.fullmatch(name) or
        name in (".", "..") or name != name.strip()):
        raise ValueError("invalid project folder")
    base = root / "Projects"
    folder = base / name
    if (base.is_symlink() or folder.is_symlink() or not folder.is_dir() or
        (folder / "project.json").is_symlink() or
        not (folder / "project.json").is_file() or
        folder.resolve().parent != base.resolve()):
        raise ValueError("unavailable project folder")
    return folder


def make_engine_client(engine_dir: Path, data_root: Path):
    """Real Engine app is constructed INSIDE this worker, never in parent."""
    if not (engine_dir / "server" / "api.py").is_file():
        raise RuntimeError("Engine submodule missing")
    if not data_root.is_dir() or data_root.is_symlink():
        raise RuntimeError("Dedicated Engine root required")
    os.environ["ZUCKER_DATA_ROOT"] = str(data_root)
    os.environ["ZUCKER_MIXER_STATE_ROOT"] = str(data_root / "Mixer" / "state")
    os.environ["MONTARA_LOCAL_DIRECTOR"] = "1"
    sys.path.insert(0, str(engine_dir))
    os.chdir(engine_dir)
    from server.api import create_app
    return create_app(project_path=None, dev=False).test_client()


def run(stdin, stdout, *, engine_dir: Path, data_root: Path, make_client=make_engine_client):
    """Only fixed operations. All statuses pass over dedicated stdio pipes."""
    client = make_client(engine_dir, data_root)
    def emit(value):
        stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
        stdout.flush()
    emit({"type": "ready", "worker_pid": os.getpid()})
    active_folder = None
    allowed_stage_statuses = {"pending", "idle", "queued", "running",
                              "done", "failed", "blocked", "not_started"}
    for raw in stdin:
        try:
            if len(raw) > 8192:
                raise ValueError("request too large")
            packet = json.loads(raw)
            if not isinstance(packet, dict):
                raise ValueError("invalid request")
            if packet.get("op") == "stop":
                emit({"ok": True, "type": "stopped"})
                return
            if packet.get("op") == "register_staged_proxies":
                # Fixed local operation, not generic paths supplied by HTTP.
                # Trusted operator copies hash-checked proxy bytes into the
                # dedicated project folder before invoking this command.
                if set(packet) != {"op"} or active_folder is None:
                    raise ValueError("Requires opened private Engine project")
                state = client.application.config.get("ZUCKER_STATE")
                loaded = getattr(getattr(state, "project", None), "folder", None)
                if not isinstance(loaded, (str, Path)) or Path(loaded).resolve() != active_folder:
                    raise ValueError("Active project changed")
                camera_dir = active_folder / "inputs" / "urano-staged-proxies"
                if camera_dir.is_symlink() or not camera_dir.is_dir():
                    raise ValueError("Trusted staged proxy directory missing")
                paths = []
                slots = set()
                for candidate in sorted(camera_dir.iterdir()):
                    match = re.fullmatch(r"camera-([0-9]|1[0-5])-([0-9a-f]{64})\.mp4", candidate.name)
                    if not match:
                        # Ignore temporary files, never register arbitrary media.
                        continue
                    slot, expected = int(match.group(1)), match.group(2)
                    if slot in slots or candidate.is_symlink() or not candidate.is_file():
                        raise ValueError("Invalid staged source")
                    digest = hashlib.sha256()
                    with candidate.open("rb") as source:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != expected:
                        raise ValueError("Staged source bytes changed")
                    slots.add(slot)
                    paths.append((slot, str(candidate)))
                if not paths or len(paths) > 16 or slots != set(range(len(paths))):
                    raise ValueError("Stage sources must have contiguous camera slots")
                result = client.post("/api/v1/inputs/videos",
                                     json={"paths": [path for _, path in sorted(paths)], "append": False})
                if result.status_code != 200:
                    emit({"ok": False, "type": "staged_inputs_rejected",
                          "http_status": result.status_code})
                    continue
                emit({"ok": True, "type": "staged_inputs_registered",
                      "source_count": len(paths)})
                continue
            if packet.get("op") == "ingest_proof":
                # Fixed authenticated stdio command. Compute the proof under
                # the Engine UID, never grant the HTTP/host process file access.
                # Only SHA-256 hashes and slot integers cross this channel.
                if set(packet) != {"op"} or active_folder is None:
                    raise ValueError("An opened private Engine project is required")
                state = client.application.config.get("ZUCKER_STATE")
                loaded = getattr(getattr(state, "project", None), "folder", None)
                if not isinstance(loaded, (str, Path)) or Path(loaded).resolve() != active_folder:
                    raise ValueError("Active Engine project changed")
                snapshot = client.get("/api/v1/project")
                if snapshot.status_code != 200:
                    raise ValueError("Engine snapshot unavailable")
                project = snapshot.get_json()
                stage = (project.get("stages") or {}).get("ingest") or {}
                if not isinstance(stage, dict) or stage.get("status") != "done":
                    raise ValueError("Stage Ingest did not finish")
                videos = (project.get("inputs") or {}).get("videos")
                if not isinstance(videos, list) or not 1 <= len(videos) <= 16:
                    raise ValueError("Stage camera count unavailable")
                proofs = []
                camera_dir = active_folder / "inputs" / "urano-staged-proxies"
                if camera_dir.is_symlink() or not camera_dir.is_dir():
                    raise ValueError("Private Engine input folder missing")
                for slot, video in enumerate(videos):
                    if not isinstance(video, dict):
                        raise ValueError("Unrecognized Engine camera")
                    raw = video.get("path")
                    norm = video.get("normalized")
                    if (not isinstance(raw, str) or not isinstance(norm, dict)
                            or not isinstance(norm.get("path"), str)):
                        raise ValueError("Engine camera or normalized output unavailable")
                    source = Path(raw)
                    normalized = Path(norm["path"])
                    match = re.fullmatch(r"camera-" + str(slot) + r"-([a-f0-9]{64})\.mp4", source.name)
                    if not match:
                        raise ValueError("Source is not a private staged camera")
                    expected = camera_dir / source.name
                    if (not source.is_absolute() or source != expected or
                            source.is_symlink() or not source.is_file()):
                        raise ValueError("Source is outside private camera folder")
                    # Normalized media must also belong to this container's
                    # dedicated storage. Reject symlinks, including ancestors.
                    if (not normalized.is_absolute() or normalized.is_symlink()
                            or not normalized.is_file() or
                            not normalized.resolve().is_relative_to(data_root.resolve())):
                        raise ValueError("Normalized media outside private worker root")
                    def sha256_file(path):
                        digest = hashlib.sha256()
                        with path.open("rb") as handle:
                            for block in iter(lambda: handle.read(1024 * 1024), b""):
                                digest.update(block)
                        return digest.hexdigest()
                    source_hash = sha256_file(source)
                    if source_hash != match.group(1):
                        raise ValueError("Stage input changed after registration")
                    proofs.append({"slot": slot, "proxy_sha256": source_hash,
                                   "normalized_sha256": sha256_file(normalized)})
                emit({"ok": True, "type": "ingest_proof", "sources": proofs})
                continue
            if packet.get("op") == "stage_snapshot":
                # Read-only, bounded status for a private Stage editor. Never
                # serialize the full project: it contains private local paths.
                if set(packet) != {"op"} or active_folder is None:
                    raise ValueError("An opened private Stage project is required")
                state = client.application.config.get("ZUCKER_STATE")
                loaded = getattr(getattr(state, "project", None), "folder", None)
                if (not isinstance(loaded, (str, Path))
                        or Path(loaded).resolve() != active_folder):
                    raise ValueError("Active Engine project changed")
                inspected = client.get("/api/v1/project")
                if inspected.status_code != 200:
                    emit({"ok": False, "type": "stage_snapshot_unavailable"})
                    continue
                project = inspected.get_json()
                if not isinstance(project, dict):
                    raise ValueError("Invalid Engine project snapshot")
                stages = project.get("stages", {})
                inputs = project.get("inputs", {})
                if not isinstance(stages, dict) or not isinstance(inputs, dict):
                    raise ValueError("Invalid Engine project structure")
                status = {}
                for stage in ("ingest", "sync", "cut", "edit", "export"):
                    item = stages.get(stage, {})
                    if not isinstance(item, dict):
                        raise ValueError("Invalid Engine stage")
                    value = item.get("status", "not_started")
                    if not isinstance(value, str) or value not in allowed_stage_statuses:
                        raise ValueError("Unrecognized Engine stage status")
                    status[stage] = value
                videos = inputs.get("videos", [])
                if not isinstance(videos, list) or len(videos) > 200:
                    raise ValueError("Invalid private camera list")
                emit({"ok": True, "type": "stage_snapshot",
                      "project": active_folder.name, "stages": status,
                      "camera_count": len(videos)})
                continue
            if packet.get("op") in ("ingest_start", "ingest_status"):
                # Strict fixed operations. No user-supplied paths, media IDs,
                # filenames, URLs or request bodies; Engine uses inputs that
                # were already provisioned by trusted infrastructure.
                if set(packet) != {"op"} or active_folder is None:
                    raise ValueError("stage command requires an opened project")
                state = client.application.config.get("ZUCKER_STATE")
                loaded = getattr(getattr(state, "project", None), "folder", None)
                if not isinstance(loaded, (str, Path)) or Path(loaded).resolve() != active_folder:
                    raise ValueError("active project changed")
                if packet["op"] == "ingest_start":
                    launched = client.post("/api/v1/stages/ingest/run")
                    if launched.status_code != 202:
                        emit({"ok": False, "type": "ingest_start_rejected",
                              "http_status": launched.status_code})
                        continue
                    emit({"ok": True, "type": "ingest_started"})
                    continue
                snapshot = client.get("/api/v1/project")
                if snapshot.status_code != 200:
                    emit({"ok": False, "type": "ingest_unavailable"})
                    continue
                stage = (snapshot.get_json() or {}).get("stages", {}).get("ingest", {})
                status = stage.get("status") if isinstance(stage, dict) else None
                if not isinstance(status, str) or status not in allowed_stage_statuses:
                    emit({"ok": False, "type": "ingest_unavailable"})
                    continue
                emit({"ok": True, "type": "ingest_status", "status": status})
                continue
            if packet.get("op") != "open" or set(packet) != {"op", "folder"}:
                raise ValueError("unsupported operation")
            folder = _project_folder(data_root, packet.get("folder"))
            reply = client.post("/api/v1/wizard/projects/open", json={"path": str(folder)})
            if reply.status_code != 200:
                emit({"ok": False, "error": "Engine rejected project", "status": reply.status_code})
                continue
            # IMPORTANT: verify the *loaded* project through the Engine rather
            # than blindly trusting an HTTP 200 or a global last_project_path.
            inspected = client.get("/api/v1/project")
            # The public snapshot is ONLY project.json and does not include
            # its folder. The private Flask state is the authoritative source.
            state = client.application.config.get("ZUCKER_STATE")
            active = getattr(state, "project", None)
            loaded = getattr(active, "folder", None)
            if (inspected.status_code != 200 or not isinstance(loaded, (Path, str)) or
                Path(loaded).resolve() != folder.resolve()):
                emit({"ok": False, "error": "Engine active project unverified"})
                continue
            active_folder = folder.resolve()
            emit({"ok": True, "type": "opened", "folder": folder.name})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            emit({"ok": False, "error": "Invalid worker command"})
        except Exception:
            # Do not expose file paths or stack traces on the wire.
            emit({"ok": False, "error": "Internal worker failure"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-dir", required=True)
    parser.add_argument("--data-root", required=True)
    args = parser.parse_args()
    engine_dir = Path(args.engine_dir).resolve()
    data_root = Path(args.data_root).resolve()
    if (not data_root.is_dir() or data_root.is_symlink() or
        not (data_root / "Projects").is_dir()):
        raise SystemExit("Dedicated Engine data root is required")
    run(sys.stdin, sys.stdout, engine_dir=engine_dir, data_root=data_root)


if __name__ == "__main__":
    main()
