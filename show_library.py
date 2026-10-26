"""Montara's reusable video shelf. Engine interaction stays behind its HTTP API."""
from __future__ import annotations
import hashlib
import json
import shutil
import threading
import uuid
from pathlib import Path
from preview_api import engine_client
from flask import jsonify, request, send_from_directory


def register_show_library(app, data_root: Path):
    root = data_root / 'ShowLibrary'
    catalog_path = root / 'catalog.json'
    lock = threading.RLock()

    def records():
        return json.loads(catalog_path.read_text()) if catalog_path.is_file() else {}

    def save(items):
        root.mkdir(parents=True, exist_ok=True)
        temporary = root / (uuid.uuid4().hex + '.json')
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2))
        temporary.replace(catalog_path)

    def public(item):
        return {key: value for key, value in item.items() if key != 'file'} | {'thumbnail': '/montara/show/shelf/' + item['id'] + '/thumbnail'}

    @app.get('/montara/show/shelf')
    def show_shelf_list():
        with lock:
            return jsonify(items=[public(item) for item in records().values() if not item.get('hidden') or request.args.get('hidden') == '1'])

    @app.post('/montara/show/shelf')
    def show_shelf_save():
        body = request.get_json(silent=True) or {}
        with engine_client(app) as engine:
            response = engine.get('/api/v1/show/video-library')
            if response.status_code != 200:
                return response.get_json(), response.status_code
            asset = next((a for a in response.get_json()['items'] if a['id'] == body.get('asset_id')), None)
            if asset is None:
                return jsonify(error={'message': 'Choose a video from the current library.'}), 404
            source = Path(asset['path'])
            if not source.is_file():
                return jsonify(error={'message': 'The source video is missing.'}), 404
            params = asset.get('params') or {}
            recipe = {key: params[key] for key in ('clip_start','matte','clip_audio','audio_mode','crop','person_scale','person_offset') if key in params}
            duration = float(asset.get('saved_duration') or min(3, asset['duration']))
            digest = hashlib.sha256()
            with source.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            sha = digest.hexdigest()
            key = hashlib.sha256(json.dumps([sha, recipe, duration], sort_keys=True).encode()).hexdigest()[:24]
            with lock:
                root.mkdir(parents=True, exist_ok=True)
                target = root / (sha + source.suffix.lower())
                if not target.exists():
                    temporary = root / (uuid.uuid4().hex + '.tmp')
                    try:
                        shutil.copyfile(source, temporary)
                        temporary.replace(target)
                    finally:
                        temporary.unlink(missing_ok=True)
                item = dict(id=key, file=target.name, name=str(body.get('name') or asset['name'])[:120], recipe=recipe, saved_duration=duration, hidden=False)
                items = records(); items[key] = item; save(items)
                thumb = engine.get('/api/v1/show/video-library/' + asset['id'] + '/thumbnail')
                if thumb.status_code == 200:
                    (root / (key + '.jpg')).write_bytes(thumb.data)
            return jsonify(item=public(item)), 201

    @app.get('/montara/show/shelf/<asset_id>/thumbnail')
    def show_shelf_thumb(asset_id):
        with lock:
            if asset_id not in records():
                return '', 404
        return send_from_directory(root, asset_id + '.jpg', mimetype='image/jpeg')

    @app.post('/montara/show/shelf/<asset_id>/use')
    def show_shelf_use(asset_id):
        with lock:
            item = records().get(asset_id)
            if item is None or item.get('hidden'):
                return jsonify(error={'message': 'This library item is not available.'}), 404
            source = root / item['file']
        with engine_client(app) as engine:
            response = engine.post('/api/v1/show/library/media', json={'path': str(source), 'project_id': (request.get_json(silent=True) or {}).get('project_id')})
            if response.status_code != 201:
                return response.get_json(), response.status_code
            asset = response.get_json()['asset']
            asset.update(saved_edit=True, saved_duration=item['saved_duration'], name=item['name'])
            asset['params'] = {**asset.get('params', {}), **item['recipe']}
            return jsonify(asset=asset)

    @app.post('/montara/show/shelf/<asset_id>/visibility')
    def show_shelf_visibility(asset_id):
        with lock:
            items = records(); item = items.get(asset_id)
            if item is None:
                return jsonify(error={'message':'That library item does not exist.'}), 404
            item['hidden'] = bool((request.get_json(silent=True) or {}).get('hidden', True)); save(items)
            return jsonify(item=public(item))
