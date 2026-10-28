import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify

from deploy import preflight, healthcheck


def private_host(monkeypatch, password):
    monkeypatch.setenv('MONTARA_PREVIEW_PASSWORD', password)
    def create(_):
        app = Flask(__name__)
        app.add_url_rule('/api/v1/wizard/status', view_func=lambda: jsonify(status='idle'))
        return app
    monkeypatch.setitem(sys.modules, 'app', SimpleNamespace(create_montara_app=create))
    spec = importlib.util.spec_from_file_location('montara_private_test',
            Path(__file__).parents[1] / 'deploy/entry.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app.test_client()


def auth(username, password):
    return {'Authorization': 'Basic ' + base64.b64encode(f'{username}:{password}'.encode()).decode()}


def test_private_host_rejects_missing_bad_and_unicode_auth_without_exposing_secret(monkeypatch):
    password = 'isolated-test-secret-123'
    client = private_host(monkeypatch, password)
    for headers in ({}, auth('montara', 'wrong'), auth('ñ', password)):
        response = client.get('/api/v1/wizard/status', headers=headers)
        assert response.status_code == 401
        assert password not in response.text
    response = client.get('/api/v1/wizard/status', headers=auth('montara', password))
    assert response.json == {'status': 'idle'}
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'


def test_private_host_refuses_short_password(monkeypatch):
    with pytest.raises(RuntimeError, match='16 characters'):
        private_host(monkeypatch, 'short')


def test_server_check_failure_is_explicit_and_report_has_no_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv('MONTARA_PREVIEW_PASSWORD', 'secret-not-for-reports')
    monkeypatch.setenv('ABACUS_API_KEY', 'never-export-this-token')
    monkeypatch.setattr(preflight, 'command', lambda *args, **kwargs: (False, ''))
    monkeypatch.setattr(preflight.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1))
    result = preflight.collect(tmp_path, server=True)
    assert result['ready'] is False
    failures = {c['name'] for c in result['checks'] if c['status'] == 'failed'}
    assert {'ffmpeg', 'ffprobe', 'disk_headroom', 'download_runtime'} <= failures
    report = json.dumps(result)
    assert 'secret-not-for-reports' not in report
    assert 'never-export-this-token' not in report
    assert str(tmp_path) not in report


def test_check_never_creates_a_desktop_editor_data_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight.Path, 'home', lambda: tmp_path)
    result = preflight.collect(tmp_path / 'ZuckerVideos' / 'nested')
    assert result['ready'] is False
    assert not (tmp_path / 'ZuckerVideos').exists()


def test_healthcheck_never_sends_a_short_or_missing_password(monkeypatch):
    monkeypatch.delenv('MONTARA_PREVIEW_PASSWORD', raising=False)
    monkeypatch.setattr(healthcheck, 'urlopen', lambda *a, **k: pytest.fail('Must not request'))
    assert healthcheck.check() is False


def test_montara_data_overrides_inherited_desktop_environment(monkeypatch, tmp_path):
    import app
    monkeypatch.chdir(Path(__file__).parents[1])
    monkeypatch.setenv('ZUCKER_DATA_ROOT', str(tmp_path / 'foreign'))
    monkeypatch.setenv('ZUCKER_MIXER_STATE_ROOT', str(tmp_path / 'foreign-mixer'))
    data = tmp_path / 'montara'
    app._prepare_environment(data)
    assert os.environ['ZUCKER_DATA_ROOT'] == str(data)
    assert os.environ['ZUCKER_MIXER_STATE_ROOT'] == str(data / 'Mixer/state')
    assert not (tmp_path / 'foreign').exists()


def test_app_rejects_desktop_data_before_loading_engine(monkeypatch, tmp_path):
    import app
    monkeypatch.setattr(app.Path, 'home', lambda: tmp_path)
    with pytest.raises(ValueError, match='separate Montara'):
        app.create_montara_app(tmp_path / 'ZuckerVideos' / 'nested')
    assert not (tmp_path / 'ZuckerVideos').exists()
