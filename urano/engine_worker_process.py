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
            if packet.get("op") != "open":
                raise ValueError("unsupported operation")
            folder = _project_folder(data_root, packet.get("folder"))
            reply = client.post("/api/v1/wizard/projects/open", json={"path": str(folder)})
            if reply.status_code != 200:
                emit({"ok": False, "error": "Engine rejected project", "status": reply.status_code})
                continue
            # IMPORTANT: verify the *loaded* project through the Engine rather
            # than blindly trusting an HTTP 200 or a global last_project_path.
            inspected = client.get("/api/v1/project")
            payload = inspected.get_json(silent=True) or {}
            loaded = payload.get("folder") or payload.get("project_path")
            if (inspected.status_code != 200 or not isinstance(loaded, str) or
                Path(loaded).resolve() != folder.resolve()):
                emit({"ok": False, "error": "Engine active project unverified"})
                continue
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
