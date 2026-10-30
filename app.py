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
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
WEB = ROOT / "web"
BRAND = WEB / "brand"
FIXTURES = ROOT / "tests" / "fixtures"
# Sample material preloaded per mode while Montara is in testing.
# Stage and Pulse: three cameras + the mixed master (no separate tracks; those are for the mixer).
SAMPLE_SETS = {
    # Stage: the song as separate instrument tracks (Montara mixes them); variant "master": the finished mix.
    "youtube_master": ["much-to-me/cam-sony.mp4", "much-to-me/cam-fixed.mp4", "much-to-me/cam-360.mp4", "much-to-me/master.mp3"],
    "reel": ["much-to-me/cam-sony.mp4", "much-to-me/cam-fixed.mp4", "much-to-me/cam-360.mp4", "much-to-me/master.mp3"],
    "show": ["real/talk.mp4"],
    "youtube": ["much-to-me/cam-sony.mp4", "much-to-me/cam-fixed.mp4", "much-to-me/cam-360.mp4"]
    + [f"much-to-me/stems/{name}.mp3" for name in (
        "Kick", "Snare", "HH", "OV", "Bass", "Guit", "KeysL", "Keys-R", "vox-1")],
}
DEFAULT_DATA = Path.home() / "MontaraData"
# Shown at the bottom of every page, so it is obvious which build is running.
MONTARA_VERSION = "0.39 · 2026-10-27 · Session mixes and resumable uploads"
BRANDING_MODES = {"montara", "mine", "none"}


def _prepare_environment(data_root: Path) -> None:
    if not (ENGINE / "server" / "api.py").is_file():
        raise SystemExit("The engine is missing. Run: git submodule update --init")
    # Montara never shares data with a local Zucker Editor install.
    os.environ["ZUCKER_DATA_ROOT"] = str(data_root)
    os.environ["MONTARA_LOCAL_DIRECTOR"]="1"
    os.environ["ZUCKER_MIXER_STATE_ROOT"] = str(data_root / "Mixer" / "state")
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
    data_root = Path(data_root).expanduser().resolve()
    desktop_data = (Path.home() / 'ZuckerVideos').resolve()
    if data_root == desktop_data or data_root.is_relative_to(desktop_data):
        raise ValueError('Choose a separate Montara data folder.')
    _prepare_environment(data_root)
    from flask import jsonify, request, send_from_directory
    from server.api import create_app
    from server.inbox import classify_paths, load_global_config

    # Re-open this preview's last project after a worker restart, without rerunning it.
    last_path=Path(str(load_global_config().get("last_project_path") or data_root/'__none__')).expanduser().resolve()
    saved_project=str(last_path) if last_path.is_relative_to(data_root.resolve()) and (last_path/'project.json').is_file() else None
    from show_editor_state import bind_editor_callbacks, register_editor_state
    bind_editor_callbacks()
    app = create_app(project_path=saved_project, dev=False)
    register_editor_state(app)
    # Swap the interface: same engine API, Montara's own pages.
    from show_library import register_show_library
    register_show_library(app, data_root)
    from green_library import register_green_library
    register_green_library(app, FIXTURES)
    from source_cache import register_source_cache
    register_source_cache(app, data_root, FIXTURES)
    from media_access import register_media_access
    register_media_access(app, remote=bool(os.environ.get("MONTARA_SESSION_TOKEN")))
    from music_shelf import register_music_shelf
    register_music_shelf(app, data_root, FIXTURES / 'music')
    from show_cut_edit import register_show_cut_edit
    register_show_cut_edit(app, data_root)
    from show_direction import register_show_direction
    register_show_direction(app, data_root)
    from show_playback import register_show_playback
    register_show_playback(app, data_root)
    from show_samples import register_show_samples, show_examples, show_inputs
    register_show_samples(app, FIXTURES, samples, data_root)
    from push_pack import register_push_pack
    register_push_pack(app, data_root, FIXTURES)
    from full_session import register_full_session
    register_full_session(app, data_root, FIXTURES)
    from resumable_upload import register_resumable_upload
    register_resumable_upload(app, data_root, classify_paths)
    from montara_ai import AIService
    app.extensions['montara_ai'] = AIService(data_root)
    app.static_folder = str(WEB)
    app.view_functions["index"] = lambda: send_from_directory(WEB, "index.html")
    app.config["MONTARA"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.before_request
    def montara_raw_camera_guard():
        if request.method != "POST" or request.path not in {"/api/v1/wizard/upload", "/api/v1/inputs/upload"}:
            return None
        from urllib.parse import unquote
        names = [unquote(request.headers.get("X-Zucker-Filename", ""))]
        if request.mimetype != "application/octet-stream":
            names += [storage.filename or "" for storage in request.files.values()]
        if any(Path(name).suffix.lower() in {".insv", ".msv", ".insp", ".lrv", ".360"} for name in names):
            return jsonify({"error": {"message": "Export a stitched 360 MP4 (equirectangular) from your camera app first. Camera-original INSV/MSV files cannot be edited here."}}), 415

    @app.after_request
    def montara_no_stale_interface(response):
        # Never let a browser keep an older interface after an update.
        if request.path in {"/", "/index.html"} or request.path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-store"
        if request.path == "/api/v1/wizard/result" or (request.path.startswith("/montara/mix/") and request.path.endswith("/result")):
            from werkzeug.http import parse_options_header
            from werkzeug.utils import secure_filename
            _, options = parse_options_header(response.headers.get("Content-Disposition", ""))
            name = secure_filename(request.args.get("download_name") or options.get("filename") or "master.mp3")
            file = Path(name)
            stem = file.stem or "master"
            if "montara" not in stem.lower():
                stem += "-Montara"
            response.headers.set("Content-Disposition", "inline", filename=stem + file.suffix)
        return response

    @app.get("/montara/show-studio")
    def montara_show_studio():
        from flask import redirect
        return redirect("/?mode=show")

    @app.get("/montara/show/sample")
    def montara_show_sample():
        if not samples:return '',404
        example=show_examples(FIXTURES).get(request.args.get("variant","normal"))
        if example:
            return send_from_directory(FIXTURES / "show",example['video'])
        return send_from_directory(FIXTURES / "real", "talk.mp4")

    @app.get("/montara/version")
    def montara_version():
        return jsonify({"version": MONTARA_VERSION})
    _apply_branding(str(load_global_config().get("montara_branding_mode") or "montara"), data_root)

    @app.get("/montara/samples")
    def montara_samples():
        """Test footage that ships with the repo, preloaded while Montara is in testing."""
        platform = request.args.get("platform", "")
        variant = request.args.get("variant", "")
        names = SAMPLE_SETS.get(f"{platform}_{variant}" if variant else platform, [])
        example=show_examples(FIXTURES).get(variant or "normal") if platform=="show" else None
        if example:names=["show/"+example['video']]
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
        classified = classify_paths(paths)
        if platform == 'reel' and not classified.get('master'):
            return jsonify(enabled=False, error={'message':'The Push example needs its song master. Please reopen the example after the update.'}), 503
        return jsonify({"enabled": True, "viewpoints": by_path, "example": example, "inputs": show_inputs(FIXTURES, variant) if example else {}, **classified})

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

    # ---- mixer: one song, separate tracks -> auto-mix -> faders -> master MP3 ----
    mix_jobs: dict[str, dict] = {}
    mix_lock = threading.Lock()  # the mixer engine keeps module-level state: one job at a time

    def _mix_worker(job_id: str, action: str, payload: dict) -> None:
        job = mix_jobs[job_id]
        with mix_lock:
            try:
                sys.path.insert(0, str(ROOT))
                from mixer_adapter.single_song import SingleSongMix

                mixer = job.get("mixer") or SingleSongMix(job["tracks_dir"], job["work_dir"])
                job["mixer"] = mixer
                if action == "analyze":
                    job["plan"] = mixer.analyze()
                else:
                    reference = payload.get("reference")
                    mixer.reference = Path(reference) if reference else None
                    out = mixer.render(payload.get("faders") or {}, job["work_dir"] / "mix.wav", payload.get("mutes") or {}, payload.get("effects"))
                    job["master"] = classify_paths([str(out)])
                    job["master_path"] = str(out)
                job["status"] = "ready" if action == "analyze" else "done"
            except Exception as exc:  # report, never crash the server
                logging.getLogger("montara.mixer").exception("Mix %s failed", action)
                job["status"] = "failed"
                job["error"] = str(exc) or exc.__class__.__name__

    def _mix_public(job: dict) -> dict:
        return {key: job.get(key) for key in ("id", "status", "error", "plan", "master_path", "reference")}

    @app.post("/montara/mix")
    def montara_mix_start():
        """Start the auto-mix for a list of registered audio tracks (paths)."""
        from mixer_adapter.source_access import resolve_mix_sources
        try:
            files = resolve_mix_sources(
                (request.get_json(silent=True) or {}).get("tracks"),
                data_root, FIXTURES,
                remote=bool(os.environ.get("MONTARA_SESSION_TOKEN")),
            )
        except ValueError as exc:
            return jsonify({"error": {"message": str(exc)}}), 400
        job_id = uuid.uuid4().hex[:12]
        work = data_root / "Mixer" / job_id
        tracks_dir = work / "tracks"
        tracks_dir.mkdir(parents=True, exist_ok=True)
        for path in files:  # the mixer reads a folder; link, never copy big files
            target = tracks_dir / path.name
            if not target.exists():
                try:
                    target.symlink_to(path)
                except OSError:
                    import shutil
                    shutil.copy2(path, target)
        mix_jobs[job_id] = {"id": job_id, "status": "analyzing", "tracks_dir": tracks_dir, "work_dir": work}
        threading.Thread(target=_mix_worker, args=(job_id, "analyze", {}), daemon=True).start()
        return jsonify(_mix_public(mix_jobs[job_id])), 202

    @app.get("/montara/mix/<job_id>")
    def montara_mix_status(job_id: str):
        job = mix_jobs.get(job_id)
        return (jsonify(_mix_public(job)), 200) if job else (jsonify({"error": {"message": "unknown mix"}}), 404)

    @app.get("/montara/mix/<job_id>/track/<path:name>")
    def montara_mix_track(job_id: str, name: str):
        """Serve one track to the browser for the live fader preview."""
        job = mix_jobs.get(job_id)
        if not job:
            return jsonify({"error": {"message": "unknown mix"}}), 404
        return send_from_directory(job["tracks_dir"], Path(name).name)

    @app.get("/montara/mix/<job_id>/result")
    def montara_mix_result(job_id: str):
        job = mix_jobs.get(job_id)
        if not job or job.get("status") != "done":
            return jsonify({"error": {"message": "The master is not ready"}}), 404
        master = Path(job["master_path"])
        return send_from_directory(master.parent, master.name, mimetype="audio/mpeg")

    @app.get("/montara/mix/<job_id>/fx/<effect>/<path:name>")
    def montara_mix_fx(job_id: str, effect: str, name: str):
        job = mix_jobs.get(job_id)
        if not job or job.get("status") not in {"ready", "done", "failed"} or not job.get("mixer"):
            return jsonify({"error": {"message": "The mix is not ready"}}), 409
        try:
            with mix_lock:
                path = job["mixer"].effect_track(name, effect)
            return send_from_directory(path.parent, path.name, mimetype="audio/wav")
        except ValueError as exc:
            return jsonify({"error": {"message": str(exc)}}), 400

    @app.post("/montara/mix/<job_id>/reference")
    def montara_mix_reference(job_id: str):
        """Optional reference song for Matchering mastering."""
        job = mix_jobs.get(job_id)
        storage = request.files.get("file")
        if not job or not storage:
            return jsonify({"error": {"message": "file is required"}}), 400
        if job.get("status") not in {"ready", "done", "failed"} or job.get("reference_import", {}).get("status") == "importing":
            return jsonify({"error": {"message": "Wait for the current mix or reference to finish."}}), 409
        target = job["work_dir"] / ("reference" + (Path(storage.filename or "").suffix or ".wav"))
        storage.save(target)
        job["reference"] = str(target)
        job["reference_import"] = {"status": "ready", "title": storage.filename}
        return jsonify(_mix_public(job))

    @app.post("/montara/mix/<job_id>/reference/link")
    def montara_mix_reference_link(job_id: str):
        job = mix_jobs.get(job_id)
        if not job:
            return jsonify({"error": {"message": "Reopen the mixer before adding a reference."}}), 404
        if job.get("status") not in {"ready", "done", "failed"} or job.get("reference_import", {}).get("status") == "importing":
            return jsonify({"error": {"message": "Wait for the current mix or reference to finish."}}), 409
        from reference_import import reference_url, import_reference
        try:
            url = reference_url((request.get_json(silent=True) or {}).get("url", ""))
        except ValueError as exc:
            return jsonify({"error": {"message": str(exc)}}), 400
        job["reference_import"] = {"status": "importing"}
        def worker():
            try:
                target, title = import_reference(url, job["work_dir"])
                job["reference"] = str(target)
                job["reference_import"] = {"status": "ready", "title": title}
            except Exception as exc:
                logging.getLogger("montara.mixer").exception("Reference import failed")
                job["reference_import"] = {"status": "failed", "message": str(exc) if isinstance(exc, ValueError) else "Could not prepare this reference. Try another link or an audio file."}
        threading.Thread(target=worker, daemon=True).start()
        return jsonify(job["reference_import"]), 202

    @app.get("/montara/mix/<job_id>/reference/link")
    def montara_mix_reference_link_status(job_id: str):
        job = mix_jobs.get(job_id)
        if not job:
            return jsonify({"error": {"message": "Reopen the mixer before adding a reference."}}), 404
        return jsonify(job.get("reference_import") or {"status": "empty"})

    @app.post("/montara/mix/<job_id>/render")
    def montara_mix_render(job_id: str):
        job = mix_jobs.get(job_id)
        if not job or job.get("status") not in {"ready", "done", "failed"}:
            return jsonify({"error": {"message": "The mix is not ready"}}), 409
        if job.get("reference_import", {}).get("status") == "importing":
            return jsonify({"error": {"message": "The reference audio is still being prepared."}}), 409
        body = request.get_json(silent=True) or {}
        payload = {"faders": body.get("faders") or {}, "mutes": body.get("mutes") or {}, "reference": job.get("reference")}
        if "effects" in body:
            from mixer_adapter.single_song import validate_effects
            try:
                payload["effects"] = validate_effects(body["effects"], [t["file"] for t in job["plan"]["tracks"]])
            except ValueError as exc:
                return jsonify({"error": {"message": str(exc)}}), 400
        job["status"] = "rendering"
        job.pop("error", None)
        threading.Thread(target=_mix_worker, args=(job_id, "render", payload), daemon=True).start()
        return jsonify(_mix_public(job)), 202

    @app.get("/montara/plans")
    def montara_plan_preview():
        return send_from_directory(WEB, "plans.html")

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
