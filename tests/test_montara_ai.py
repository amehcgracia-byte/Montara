"""Structured provider boundary; fake responses never count as real Abacus tests."""
import json
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from montara_ai import AIService
from ai_tasks import GAMER_EMPHASES, SESSION_BOUNDARIES


@pytest.fixture(autouse=True)
def fake_config(monkeypatch):
    monkeypatch.setenv('MONTARA_LLM_MODEL', 'test-model')
    monkeypatch.setenv('MONTARA_LLM_API_KEY', 'test-placeholder')
    monkeypatch.delenv('ABACUS_API_KEY', raising=False)
    monkeypatch.delenv('MONTARA_AI_ENABLED', raising=False)


EVIDENCE = dict(phrases=[{'id': 1, 'text': 'This is the turning point.'}], maximum=2)


def response(value):
    return dict(choices=[dict(finish_reason='stop', message=dict(content=json.dumps(value)))],
                usage=dict(prompt_tokens=40, completion_tokens=10))


def test_no_key_means_no_call_and_no_fake_review(tmp_path, monkeypatch):
    monkeypatch.delenv('MONTARA_LLM_API_KEY')
    def forbidden(_):
        pytest.fail('No network request may happen without credentials')
    assert AIService(tmp_path, send=forbidden).review(GAMER_EMPHASES, EVIDENCE) == {'status': 'not_configured'}
    assert not (tmp_path / 'AI').exists()


def test_validated_cache_reuse_has_zero_additional_tokens(tmp_path):
    calls = []
    service = AIService(tmp_path, send=lambda body: calls.append(body) or response({'emphases': [{'id': 1, 'reason': 'Turning point'}]}))
    first = service.review(GAMER_EMPHASES, EVIDENCE)
    second = service.review(GAMER_EMPHASES, EVIDENCE)
    assert first['status'] == 'reviewed' and not first['cached'] and second['cached']
    assert len(calls) == 1
    assert str(tmp_path) not in json.dumps(calls) and 'test-placeholder' not in json.dumps(calls)
    with sqlite3.connect(tmp_path / 'AI/reasoning.sqlite') as db:
        assert db.execute('SELECT status,input_tokens,output_tokens FROM usage ORDER BY id').fetchall() == [('reviewed', 40, 10), ('cache_hit', 0, 0)]


@pytest.mark.parametrize('invalid', [
    {'emphases': [{'id': 999, 'reason': 'Invented phrase'}]},
    {'emphases': [{'id': 1, 'reason': 'A', 'start': 100}]},
    {'emphases': [{'id': True, 'reason': 'A'}]},
    {'emphases': [{'id': 1, 'reason': 'A'}, {'id': 1, 'reason': 'B'}]},
    {'emphases': [], 'command': 'execute arbitrary code'},
])
def test_invalid_decisions_do_not_reach_timeline_but_usage_is_recorded(tmp_path, invalid):
    result = AIService(tmp_path, send=lambda _: response(invalid)).review(GAMER_EMPHASES, EVIDENCE)
    assert result['status'] == 'invalid_response' and result['value'] is None
    with sqlite3.connect(tmp_path / 'AI/reasoning.sqlite') as db:
        assert db.execute('SELECT input_tokens,output_tokens FROM usage').fetchone() == (40, 10)


def test_timeout_does_not_claim_zero_provider_cost_or_repeat_request(tmp_path):
    calls = []
    def timeout(body):
        calls.append(body); raise TimeoutError('private provider diagnostic')
    service = AIService(tmp_path, send=timeout)
    assert service.review(GAMER_EMPHASES, EVIDENCE)['status'] == 'timeout'
    assert service.review(GAMER_EMPHASES, EVIDENCE)['status'] == 'timeout'
    assert len(calls) == 1
    with sqlite3.connect(tmp_path / 'AI/reasoning.sqlite') as db:
        assert db.execute('SELECT input_tokens,output_tokens FROM usage').fetchone() == (None, None)


def test_inflight_identical_request_is_not_duplicated(tmp_path):
    started = threading.Event(); release = threading.Event(); calls = []
    def send(body):
        calls.append(body); started.set(); release.wait(timeout=5)
        return response({'emphases': []})
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(AIService(tmp_path, send=send).review, GAMER_EMPHASES, EVIDENCE)
        assert started.wait(timeout=3)
        try:
            assert AIService(tmp_path, send=send).review(GAMER_EMPHASES, EVIDENCE)['status'] == 'busy'
        finally:
            release.set()
        assert pending.result(timeout=5)['status'] == 'reviewed'
    assert len(calls) == 1


def test_boundary_review_requires_every_supplied_id_and_forbids_new_coordinates():
    evidence = {'cuts': [{'id': 2}, {'id': 5}]}
    with pytest.raises(ValueError):
        SESSION_BOUNDARIES.validate({'cuts': [{'id': 2, 'decision': 'plausible', 'reason': 'Rest'}], 'summary': 'Incomplete'}, evidence)
    result = SESSION_BOUNDARIES.validate({'cuts': [dict(id=2, decision='plausible', reason='Rest'), dict(id=5, decision='review', reason='May be a bridge')], 'summary': 'Check the second cut'}, evidence)
    assert result['cuts'][1]['decision'] == 'review'


def test_real_http_contract_through_disposable_transport_process(tmp_path, monkeypatch):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            body = json.dumps(response({'emphases': []})).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    monkeypatch.setenv('MONTARA_LLM_BASE_URL', f'http://127.0.0.1:{server.server_port}/v1')
    try:
        result = AIService(tmp_path).review(GAMER_EMPHASES, EVIDENCE)
        assert result['status'] == 'reviewed'
        assert requests[0][0] == '/v1/chat/completions'
        assert requests[0][1]['response_format'] == {'type': 'json_object'}
        assert requests[0][1]['max_tokens'] == 1800
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_session_worker_uses_shared_review_without_uploading_audio(tmp_path, monkeypatch):
    import time
    import numpy as np
    import soundfile as sf
    from flask import Flask
    from full_session import register_full_session
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            evidence=json.loads(request['messages'][1]['content']); received.append(evidence)
            value={'cuts':[dict(id=cut['id'],decision='review',reason='Synthetic contract review') for cut in evidence['cuts']], 'summary':'Check the proposed rest'}
            body=json.dumps(response(value)).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('MONTARA_LLM_BASE_URL',f'http://127.0.0.1:{server.server_port}/v1')
    root=tmp_path/'data';root.mkdir()
    sr=8000;t=np.arange(sr*150)/sr
    active=(t<65)|(t>85)
    source=root/'Bass.wav';sf.write(source,.1*np.sin(2*np.pi*160*t)*active,sr)
    app=Flask(__name__);register_full_session(app,root,tmp_path/'fixtures');client=app.test_client()
    try:
        job=client.post('/montara/session',json={'tracks':[str(source)]}).json
        for _ in range(200):
            state=client.get('/montara/session/'+job['id']).json
            if state['status'] not in {'detecting'}:break
            time.sleep(.1)
        assert state['status']=='review',state
        assert state['ai_review']['status']=='reviewed',state
        assert len(state['songs'])==2
        assert state['songs'][0]['review_note']=='Synthetic contract review'
        assert received and str(tmp_path) not in json.dumps(received)
        assert 'tracks' not in received[0] and 'audio' not in received[0]
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
