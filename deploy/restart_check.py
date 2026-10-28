"""CI check on an isolated test host: project and video survive web restart."""
import base64
import json
import os
from urllib.request import Request, urlopen


def get(path):
    encoded = base64.b64encode(('montara:' + os.environ['MONTARA_PREVIEW_PASSWORD']).encode()).decode()
    return urlopen(Request('http://127.0.0.1:8080' + path,
                          headers={'Authorization': 'Basic ' + encoded}), timeout=30)


def check():
    with get('/api/v1/project') as response:
        project = json.load(response)
    assert (project.get('inputs') or {}).get('videos'), 'Project sources were not recovered'
    with get('/api/v1/wizard/status') as response:
        status = json.load(response)
    assert status.get('result'), 'The previous export was not recovered'
    with get('/api/v1/wizard/result') as response:
        assert response.status == 200 and len(response.read(2048)) == 2048, 'Export is unavailable'
    print('Persisted sources, project and exported video available after web restart.')


if __name__ == '__main__':
    check()
