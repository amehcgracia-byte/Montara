"""Single-user private beta launcher: deliberately NOT the URANO multiowner runtime.

A private HTTPS public beta needs a separate authorized deployment. This
launcher binds the complete existing Montara editor to loopback only, with
private filesystem and Basic Auth, for use through an authenticated SSH tunnel.
It never installs packages, changes systemd, enables ports, or touches Chema's
services. Use --init, then --check, then --serve from an isolated checkout.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import socket
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESERVED_PORTS = {8090, 8101, 8102, 8103}
DEFAULT_PORT = 8114


def _default_locations(home: Path) -> tuple[Path, Path]:
    return (home / "montara-personal-beta-data",
            home / ".config" / "montara-personal-beta" / "credentials.json")


def _private_path(path: Path, home: Path, *, directory: bool = False) -> Path:
    if not path.is_absolute() or path == home or not path.is_relative_to(home):
        raise ValueError("Personal beta files must stay inside the operator's home")
    if path.is_symlink() or (directory and not path.is_dir()):
        raise ValueError("Personal beta path unavailable or linked")
    if not directory and not path.is_file():
        raise ValueError("Private credentials file missing")
    current = path
    while current != home:
        if current.is_symlink():
            raise ValueError("Symlinked parent directory forbidden")
        current = current.parent
    details = path.stat()
    if hasattr(os, "getuid") and details.st_uid != os.getuid():
        raise ValueError("Personal beta files belong to another user")
    if details.st_mode & 0o077:
        raise ValueError("Personal beta data and credentials require 0700/0600")
    return path


def _port(port: int) -> int:
    if type(port) is not int or not 1024 <= port <= 65535 or port in RESERVED_PORTS:
        raise ValueError("Choose a dedicated unprivileged beta port")
    return port


def check_private_beta(data: Path, credential_file: Path, *, home: Path,
                       port: int) -> dict:
    """Read-only readiness. No secrets, user paths, usernames or tokens in report."""
    if os.name != "posix" or (hasattr(os, "getuid") and os.getuid() == 0):
        raise ValueError("Single-user beta requires a nonroot POSIX account")
    _port(port)
    data = _private_path(data, home, directory=True)
    credential_file = _private_path(credential_file, home)
    if not credential_file.is_relative_to(home / ".config"):
        raise ValueError("Credentials must remain in private user config")
    if data == credential_file.parent or data.is_relative_to(ROOT.resolve()):
        raise ValueError("Beta data cannot overlap source code or config")
    if data == (home / "ZuckerVideos") or data.is_relative_to(home / "ZuckerVideos"):
        raise ValueError("Cannot use existing ZuckerVideos data")
    if not (ROOT / "engine" / "server" / "api.py").is_file():
        raise ValueError("Pinned Engine submodule unavailable")
    if not (ROOT / "mixer" / "jam_mix_pipeline.py").is_file():
        raise ValueError("Pinned Mixer submodule unavailable")
    if sys.version_info[:2] != (3, 11):
        raise ValueError("Beta uses Python 3.11")
    doc = json.loads(credential_file.read_text(encoding="utf-8"))
    if (not isinstance(doc, dict) or set(doc) != {"username", "password"}
            or doc["username"] != "montara"
            or not isinstance(doc["password"], str)
            or len(doc["password"]) < 16):
        raise ValueError("Private beta credentials invalid")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
    return {"ready_for_single_user_tunnel": True,
            "access": "127.0.0.1-only",
            "multiowner_isolation": False,
            "public_https_deployed": False,
            "checks": ["private_storage", "private_credentials", "engine_pin",
                       "mixer_pin", "python_3_11", "loopback_port_available"]}


def init_private_beta(data: Path, credential_file: Path, *, home: Path) -> None:
    if not data.is_absolute() or not data.is_relative_to(home) or data == home:
        raise ValueError("Invalid private data directory")
    if not credential_file.is_relative_to(home / ".config"):
        raise ValueError("Invalid private credentials destination")
    if data.is_symlink() or credential_file.exists() or credential_file.is_symlink():
        raise ValueError("Existing private beta credentials/data require manual review")
    # Never follow pre-existing symlinked config directories.
    for folder in (home / ".config", credential_file.parent, data):
        if folder.is_symlink():
            raise ValueError("Symlinked beta folder forbidden")
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if folder != home / ".config":
            folder.chmod(0o700)
    if not (home / ".config").is_dir():
        raise ValueError("Private configuration root unavailable")
    pwd = getpass.getpass("Create private Montara beta password (16+ chars): ")
    if len(pwd) < 16:
        raise ValueError("Use a longer beta password")
    doc = json.dumps({"username": "montara", "password": pwd}).encode("utf-8")
    fd = os.open(str(credential_file),
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(doc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    ops = parser.add_mutually_exclusive_group(required=True)
    ops.add_argument("--init", action="store_true")
    ops.add_argument("--check", action="store_true")
    ops.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    home = Path.home().resolve()
    data, credentials = _default_locations(home)
    try:
        _port(args.port)
        if args.init:
            init_private_beta(data, credentials, home=home)
            print("Private beta initialized. Run --check next.")
            return 0
        report = check_private_beta(data, credentials, home=home, port=args.port)
        if args.check:
            print(json.dumps(report, sort_keys=True))
            return 0
        doc = json.loads(credentials.read_text(encoding="utf-8"))
        env = {**os.environ, "MONTARA_DATA": str(data),
               "MONTARA_PREVIEW_USER": doc["username"],
               "MONTARA_PREVIEW_PASSWORD": doc["password"],
               "MONTARA_AI_ENABLED": "0"}
        # Existing runtime may call os.chdir(engine); gunicorn loads
        # deploy.entry with precisely ONE process (global Engine state).
        os.execvpe(sys.executable,
                   [sys.executable, "-m", "gunicorn",
                    "--chdir", str(ROOT), "--bind", f"127.0.0.1:{args.port}",
                    "--workers", "1", "--threads", "8", "--timeout", "1800",
                    "deploy.entry:app"], env)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        # Do not leak paths or credentials into untrusted CI/run logs.
        print("Personal beta gate rejected:", type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
