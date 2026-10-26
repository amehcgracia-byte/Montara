from flask import Flask,jsonify
from media_access import register_media_access


def client(remote=True):
    app=Flask(__name__);register_media_access(app,remote=remote)
    @app.post('/api/v1/show/references/video/one/download')
    def download():
        return jsonify(error={'code':'clip_download_failed','message':"YouTube needs a browser verification, not more credits. Select that browser."}),502
    @app.post('/api/v1/show/library/media')
    def upload():return jsonify(asset={'id':'file'}),201
    @app.post('/api/v1/show/other')
    def other():return jsonify(error={'code':'invalid_reference','message':'Wrong interval'}),400
    return app.test_client()


def test_cloud_verification_is_actionable_and_not_retrying():
    c=client();r=c.post('/api/v1/show/references/video/one/download')
    assert r.status_code==422
    assert r.json['error']['code']=='external_verification_required'
    assert r.json['error']['retryable'] is False
    assert 'Upload a video file' in r.json['error']['message']
    assert 'Select that browser' not in r.json['error']['message']
    assert r.headers['Cache-Control']=='no-store'
    assert c.post('/api/v1/show/library/media').status_code==201
    assert c.post('/api/v1/show/other').json['error']['code']=='invalid_reference'


def test_local_browser_download_advice_is_unchanged():
    r=client(False).post('/api/v1/show/references/video/one/download')
    assert r.status_code==502
    assert 'Select that browser' in r.json['error']['message']
