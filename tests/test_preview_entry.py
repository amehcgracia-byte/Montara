import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from flask import Flask


def test_external_browser_gets_public_entry_link_without_access_to_another_session(monkeypatch):
    def create(_):
        app=Flask(__name__)
        app.add_url_rule('/',view_func=lambda:'private editor')
        return app
    monkeypatch.setitem(sys.modules,'app',SimpleNamespace(create_montara_app=create))
    monkeypatch.setenv('MONTARA_SESSION_TOKEN','a'*32)
    spec=importlib.util.spec_from_file_location('preview_test_entry',Path(__file__).parents[1]/'deploy/sandbox_entry.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    client=module.app.test_client()
    result=client.get('/',base_url='https://example.test')
    assert result.status_code==401
    assert 'href="https://montara-tau.vercel.app/"' in result.text
    assert 'a'*32 not in result.text
    assert client.get('/_preview/grant?token=wrong').status_code==403
    grant=client.get('/_preview/grant?token='+'a'*32,base_url='https://example.test')
    assert grant.status_code==303
    assert client.get('/',base_url='https://example.test').text=='private editor'
    assert module.app.test_client().get('/',base_url='https://example.test').status_code==401
