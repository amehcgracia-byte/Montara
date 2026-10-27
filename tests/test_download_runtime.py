import os
from deploy import download_runtime as runtime


def test_runtime_path_is_inherited_once_without_dropping_existing_tools(monkeypatch):
    monkeypatch.setenv('PATH', '/usr/local/bin:/usr/bin')
    runtime.enable_runtime()
    runtime.enable_runtime()
    assert os.environ['PATH'].split(os.pathsep) == [
        str(runtime.ROOT / 'node_modules/.bin'), '/usr/local/bin', '/usr/bin']


def test_broken_runtime_prevents_success_report(monkeypatch, tmp_path):
    import subprocess
    import pytest
    monkeypatch.setattr(runtime, 'ROOT', tmp_path)
    deno = tmp_path / 'node_modules/.bin/deno'
    deno.parent.mkdir(parents=True)
    deno.touch()
    versions = {'yt-dlp': runtime.YTDLP, 'yt-dlp-ejs': runtime.EJS}
    monkeypatch.setattr(runtime.importlib.metadata, 'version', versions.__getitem__)
    monkeypatch.setattr(runtime.subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, stdout='deno 0.0.0 (unexpected)'))
    with pytest.raises(RuntimeError, match='Unexpected'):
        runtime.ensure_runtime()
