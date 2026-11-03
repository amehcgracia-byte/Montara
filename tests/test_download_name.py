"""The HTTP header must agree with the UI, including non-ASCII project names."""
import sys
from pathlib import Path
from urllib.parse import urlencode
import pytest
from flask import send_file
from werkzeug.http import parse_options_header
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize('name',['Take 03.mp4','Montara.Notetaker.mp4','Sesión de José.mp4'])
def test_video_download_header_keeps_project_name(tmp_path,name):
    from app import create_montara_app
    app=create_montara_app(tmp_path/'data',samples=False)
    media=tmp_path/'job-9ac0-internal-0042.mp4';media.write_bytes(b'video payload')
    endpoint=next(rule.endpoint for rule in app.url_map.iter_rules() if rule.rule=='/api/v1/wizard/result')
    app.view_functions[endpoint]=lambda:send_file(media)
    response=app.test_client().get('/api/v1/wizard/result?'+urlencode({'download_name':name}))
    disposition,options=parse_options_header(response.headers['Content-Disposition'])
    assert response.status_code==200 and response.data==b'video payload'
    assert disposition=='attachment' and options['filename']==name
