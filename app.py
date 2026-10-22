"""Montara server.

Montara is a separate product built on top of the Zucker Editor engine.
The engine lives in ./engine as a git submodule pinned to an exact commit and
is NEVER modified from this repository. Montara only:
  * serves its own web interface (./web) instead of Zucker's,
  * keeps its own data folder (never ~/ZuckerVideos),
  * reuses the engine's HTTP API (/api/v1/...) unchanged.

Run:  python app.py [--host 127.0.0.1] [--port 8080]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
WEB = ROOT / "web"
DEFAULT_DATA = Path.home() / "MontaraData"


def _prepare_environment(data_root: Path) -> None:
    if not (ENGINE / "server" / "api.py").is_file():
        raise SystemExit("The engine is missing. Run: git submodule update --init")
    # Montara never shares data with a local Zucker Editor install.
    os.environ.setdefault("ZUCKER_DATA_ROOT", str(data_root))
    data_root.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ENGINE))
    # The engine resolves bundled assets relative to its own folder.
    os.chdir(ENGINE)


def create_montara_app(data_root: Path = DEFAULT_DATA):
    _prepare_environment(data_root)
    from flask import send_from_directory
    from server.api import create_app

    app = create_app(dev=False)
    # Swap the interface: same engine API, Montara's own pages.
    app.static_folder = str(WEB)
    app.view_functions["index"] = lambda: send_from_directory(WEB, "index.html")
    app.config["MONTARA"] = True
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Montara server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("MONTARA_DATA", DEFAULT_DATA)))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = create_montara_app(args.data.expanduser().resolve())
    logging.getLogger("montara").info("Montara on http://%s:%s (data: %s)", args.host, args.port, args.data)
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
