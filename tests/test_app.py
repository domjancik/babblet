import importlib.util


def test_local_read_only_display_snapshot_and_health():
    assert importlib.util.find_spec('babblet.web'), 'Display server must exist'
    from fastapi.testclient import TestClient
    from babblet.core import Pipeline
    from babblet.web import create_app
    client = TestClient(create_app(Pipeline(None)))
    assert client.get('/api/snapshot').json()['utterances'] == []
    assert client.get('/healthz').json()['pipeline']['pending'] == 0
    response = client.get('/')
    assert 'Babblet' in response.text
    assert "default-src 'self'" in response.headers['content-security-policy']
    assert client.post('/api/snapshot').status_code == 405


def test_rejects_foreign_host_and_origin():
    from fastapi.testclient import TestClient
    from babblet.core import Pipeline
    from babblet.web import create_app
    client = TestClient(create_app(Pipeline(None)))
    assert client.get('/api/snapshot', headers={'Host': 'evil.example'}).status_code == 400
    assert client.get('/api/snapshot', headers={'Origin': 'https://evil.example'}).status_code == 403
