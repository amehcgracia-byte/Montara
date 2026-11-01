"""Private review host for the complete, unchanged Montara application.
Single worker is intentional: the original engine owns a single current project.
"""
import hmac
import os
from pathlib import Path
from flask import Response, request
from app import create_montara_app
password = os.environ.get("MONTARA_PREVIEW_PASSWORD", "")
username = os.environ.get("MONTARA_PREVIEW_USER", "montara")
if len(password) < 16:
    raise RuntimeError("Set a preview password of at least 16 characters before starting.")
app = create_montara_app(Path(os.environ.get("MONTARA_DATA", "/data")))
@app.before_request
def private_review_access():
    auth = request.authorization
    if not auth or not hmac.compare_digest((auth.username or "").encode(), username.encode()) or not hmac.compare_digest((auth.password or "").encode(), password.encode()):
        return Response("Private Montara review", 401, {"WWW-Authenticate": 'Basic realm="Montara review"', "Cache-Control": "no-store"})
@app.after_request
def private_review_headers(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
