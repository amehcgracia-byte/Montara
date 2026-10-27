"""One isolated preview runtime per browser. No host files or account keys mounted."""
import hmac
import os
from pathlib import Path
from flask import Response, request, redirect
from deploy.download_runtime import enable_runtime

enable_runtime()
from app import create_montara_app

secret=os.environ.get('MONTARA_SESSION_TOKEN','')
if len(secret)<32:raise RuntimeError('A private session token is required.')
data_root=Path('/vercel/sandbox/data')
app=create_montara_app(data_root)
app.config['MAX_CONTENT_LENGTH']=256*1024*1024
allowed=(data_root.resolve(),(Path(__file__).resolve().parents[1]/'tests/fixtures').resolve())

@app.before_request
def preview_access():
    if request.path=='/_preview/grant':
        if not hmac.compare_digest(request.args.get('token',''),secret):return 'This preview link is not valid.',403
        response=redirect('/'+('?' + request.args['next'] if request.args.get('next') else ''),303)
        response.set_cookie('montara_preview',secret,secure=True,httponly=True,samesite='Lax',max_age=7*86400)
        return response
    if not hmac.compare_digest(request.cookies.get('montara_preview',''),secret):
        return Response("""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Abrir Montara</title><body style="background:#0b0b0d;color:#f5f3ef;font-family:system-ui;max-width:32rem;margin:15vh auto;padding:24px"><h1>Abre tu prueba de Montara</h1><p>Este enlace pertenece a una sesión de otro navegador o ya ha caducado. Cada persona tiene su propio espacio.</p><a href="https://montara-tau.vercel.app/" style="display:inline-block;background:#ff4f2e;color:white;padding:14px 22px;border-radius:24px;text-decoration:none">Abrir Montara</a><p>Comparte la dirección montara-tau.vercel.app para que otra persona pueda probarla.</p></body></html>""",401,mimetype='text/html')
    path=request.path
    if path.startswith('/api/v1/'):
        route=path[len('/api/v1/'):]
        music = (route == 'music/library' and request.method == 'GET' or route == 'music/import' and request.method == 'POST' or route.startswith('music/file/') and request.method in {'GET','HEAD'} or route.startswith('music/place/') and request.method == 'POST')
        if not (music or route=='project' or route.startswith(('wizard/','edit/','captions/','show/')) or route in {'settings/camera-roles','settings/camera-subjects','settings/camera-types','settings/spherical-landmarks'}):return 'Unavailable in this preview.',404
        if route in {'show/references/open','wizard/open-folder','wizard/open-output'}:return 'Unavailable in this preview.',404
    # File-bearing fields can reference only this session's data and the bundled inputs.
    def check(value):
        if isinstance(value,str) and value.startswith('/'):
            candidate=Path(value).resolve()
            return any(candidate.is_relative_to(root) for root in allowed)
        if isinstance(value,dict):return all(check(v) for v in value.values())
        if isinstance(value,list):return all(check(v) for v in value)
        return True
    body=request.get_json(silent=True) if request.is_json else None
    if not check(body) or not check(dict(request.args)):return 'Choose media from your own preview session.',400

@app.after_request
def preview_headers(response):
    response.headers['X-Robots-Tag']='noindex, nofollow'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response
