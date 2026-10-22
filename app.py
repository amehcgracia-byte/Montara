"""Montara server.

Montara is a separate product built on top of the Zucker Editor engine.
The engine lives in ./engine as a git submodule pinned to an exact commit and
is NEVER modified from this repository. Montara only:
  * serves its own web interface (./web) instead of Zucker's,
  * keeps its own data folder (never ~/ZuckerVideos),
  * sets the engine's branding to Montara (no ZuckerZauber card or logo),
  * reuses the engine's HTTP API (/api/v1/...) unchanged.

Run:  python app.py [--host 127.0.0.1] [--port 8080]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
WEB = ROOT / "web"
BRAND = WEB / "brand"
FIXTURES = ROOT / "tests" / "fixtures"
# Sample material preloaded per mode while Montara is in testing.
# Stage and Pulse: three cameras + the mixed master (no separate tracks; those are for the mixer).
SAMPLE_SETS = {
    "youtube": ["much-to-me/cam-sony.mp4", "much-to-me/cam-fixed.mp4", "much-to-me/cam-360.mp4", "much-to-me/master.mp3"],
    "reel": ["much-to-me/cam-sony.mp4", "much-to-me/cam-fixed.mp4", "much-to-me/cam-360.mp4", "much-to-me/master.mp3"],
    "show": ["real/talk.mp4"],
}
DEFAULT_DATA = Path.home() / "MontaraData"
BRANDING_MODES = {"montara", "mine", "none"}


def _prepare_environment(data_root: Path) -> None:
    if not (ENGINE / "server" / "api.py").is_file():
        raise SystemExit("The engine is missing. Run: git submodule update --init")
    # Montara never shares data with a local Zucker Editor install.
    os.environ.setdefault("ZUCKER_DATA_ROOT", str(data_root))
    data_root.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ENGINE))
    # The engine resolves bundled assets relative to its own folder.
    os.chdir(ENGINE)


def _apply_branding(mode: str, data_root: Path) -> dict:
    """Write the engine's branding override. Montara assets replace Zucker's;
    'mine' uses the uploaded logo; 'none' removes watermark, intro and outro."""
    from server.inbox import load_global_config, save_global_config

    config = load_global_config()
    config["branding"] = {
        "mode": "none" if mode == "none" else ("custom" if mode == "mine" else "default"),
        "logo_path": str(BRAND / "montara-logo.png"),
        "watermark_path": str(BRAND / "montara-watermark.png"),
        "intro_card": False,
    }
    mine = data_root / "Branding" / "my-logo.png"
    if mode == "mine" and mine.is_file():
        config["personal_logo_path"] = str(mine)
    else:
        config.pop("personal_logo_path", None)
    config["montara_branding_mode"] = mode
    save_global_config(config)
    return {"mode": mode, "has_logo": mine.is_file()}


def create_montara_app(data_root: Path = DEFAULT_DATA, samples: bool = True):
    _prepare_environment(data_root)
    from flask import jsonify, request, send_from_directory
    from server.api import create_app
    from server.inbox import classify_paths, load_global_config

    app = create_app(dev=False)
    # Swap the interface: same engine API, Montara's own pages.
    app.static_folder = str(WEB)
    app.view_functions["index"] = lambda: send_from_directory(WEB, "index.html")
    app.config["MONTARA"] = True
    _apply_branding(str(load_global_config().get("montara_branding_mode") or "montara"), data_root)

    @app.get("/montara/samples")
    def montara_samples():
        """Test footage that ships with the repo, preloaded while Montara is in testing."""
        platform = request.args.get("platform", "")
        names = SAMPLE_SETS.get(platform, [])
        files = [FIXTURES / name for name in names if (FIXTURES / name).is_file()]
        if not samples or not files:
            return jsonify({"enabled": False})
        paths = [str(path) for path in files]
        by_path = {}
        for folder in {path.parent for path in files}:
            viewpoints_file = folder / "viewpoints.json"
            if viewpoints_file.is_file():
                for name, value in json.loads(viewpoints_file.read_text()).items():
                    by_path[str(folder / name)] = value
        return jsonify({"enabled": True, "viewpoints": by_path, **classify_paths(paths)})

    @app.get("/montara/branding")
    def montara_branding_get():
        mode = str(load_global_config().get("montara_branding_mode") or "montara")
        return jsonify({"mode": mode, "has_logo": (data_root / "Branding" / "my-logo.png").is_file()})

    @app.post("/montara/branding")
    def montara_branding_set():
        mode = str((request.get_json(silent=True) or {}).get("mode") or "montara")
        if mode not in BRANDING_MODES:
            return jsonify({"error": {"message": "mode must be montara, mine or none"}}), 400
        if mode == "mine" and not (data_root / "Branding" / "my-logo.png").is_file():
            return jsonify({"error": {"message": "Upload your logo first"}}), 400
        return jsonify(_apply_branding(mode, data_root))

    @app.post("/montara/logo")
    def montara_logo():
        """Store the person's logo as a PNG (transparent background recommended)."""
        storage = request.files.get("file")
        if not storage:
            return jsonify({"error": {"message": "file is required"}}), 400
        from PIL import Image

        target = data_root / "Branding" / "my-logo.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            image = Image.open(storage.stream).convert("RGBA")
        except Exception:
            return jsonify({"error": {"message": "That file is not an image"}}), 400
        image.thumbnail((1600, 1600))
        image.save(target)
        return jsonify({"has_logo": True, **_apply_branding("mine", data_root)})

    @app.get("/montara/logo")
    def montara_logo_get():
        return send_from_directory(data_root / "Branding", "my-logo.png")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Montara server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("MONTARA_DATA", DEFAULT_DATA)))
    parser.add_argument("--no-samples", action="store_true", help="do not preload the test footage")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    data_root = args.data.expanduser().resolve()
    app = create_montara_app(data_root, samples=not args.no_samples)
    logging.getLogger("montara").info("Montara on http://%s:%s (data: %s)", args.host, args.port, data_root)
    app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
