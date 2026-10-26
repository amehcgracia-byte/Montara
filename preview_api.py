"""Authenticate Montara's own internal HTTP API calls in private review runtimes."""
import os

def engine_client(app):
    client=app.test_client()
    token=os.environ.get('MONTARA_SESSION_TOKEN')
    if token:client.set_cookie('montara_preview',token)
    return client
