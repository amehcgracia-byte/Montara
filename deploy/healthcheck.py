"""Authenticated, read-only container probe. Never prints the password or state."""
import base64
import os
from urllib.request import Request, urlopen


def check():
    password = os.environ.get('MONTARA_PREVIEW_PASSWORD', '')
    if len(password) < 16:
        return False
    encoded = base64.b64encode(('montara:' + password).encode()).decode()
    request = Request('http://127.0.0.1:8080/api/v1/wizard/status',
                      headers={'Authorization': 'Basic ' + encoded})
    try:
        with urlopen(request, timeout=4) as response:
            return response.status == 200 and response.headers.get_content_type() == 'application/json'
    except Exception:
        return False


if __name__ == '__main__':
    raise SystemExit(0 if check() else 1)
