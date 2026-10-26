"""Translate desktop-only download advice into an actionable cloud error.

Does not bypass site checks, transfer browser cookies or solve challenges.
"""
from flask import jsonify, request


def verification_required(message):
    lower=str(message).lower()
    return any(term in lower for term in ('not a bot','browser verification',"confirm you're",'confirm you’re','captcha'))


def register_media_access(app, remote=False):
    @app.after_request
    def cloud_download_error(response):
        if not remote or response.status_code < 400 or request.method != 'POST':
            return response
        if not request.path.startswith('/api/v1/show/'):
            return response
        data=response.get_json(silent=True)
        error=data.get('error') if isinstance(data,dict) else None
        if not isinstance(error,dict) or not verification_required(error.get('message','')):
            return response
        result=jsonify(error={
            'code':'external_verification_required',
            'message':'YouTube blocked this server download. No clip was imported. Opening YouTube on your phone or computer does not authorise the Montara server. Upload a video file you are authorised to use instead.',
            'retryable':False,
            'actions':['upload_file','open_source'],
        })
        result.status_code=422
        result.headers['Cache-Control']='no-store'
        return result
