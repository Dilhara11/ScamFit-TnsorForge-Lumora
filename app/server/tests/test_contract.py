import asyncio
from dataclasses import replace
import json
from fastapi.testclient import TestClient
import pytest
from svo_api.main import create_app
from svo_api.settings import Settings


def test_health_contract_and_errors(client):
    assert client.get('/health/ready').json()['model_version'] == 'svo-38879254a924'
    assert client.get('/api/v1/model').json()['scores_calibrated'] is False
    assert client.get('/api/v1/monitoring').json()['event_count'] == 0
    cases = [({},422), ({'text':'x','event_id':1},422), ({'text':' ','event_id':'a'},422),
             ({'text':'x','event_id':'a','label':'scam'},422),
             ({'text':'x'*10001,'event_id':'a'},422), ({'text':'\ud800','event_id':'a'},422)]
    for body, expected in cases:
        response = client.post('/api/v1/predictions', content=json.dumps(body), headers={'Content-Type':'application/json'})
        assert response.status_code == expected
        assert response.json()['error']['request_id'] == response.headers['x-request-id']
        assert 'input' not in response.text
    assert client.post('/api/v1/predictions', content='{', headers={'Content-Type':'application/json'}).status_code == 400
    assert client.post('/api/v1/predictions', content='{}').status_code == 415
    assert client.post('/api/v1/predictions', content='x'*65537, headers={'Content-Type':'application/json'}).status_code == 413
    assert client.get('/missing').status_code == 404
    assert client.get('/api/v1/clusters?limit=101').status_code == 422
    assert client.get('/api/v1/clusters/999').status_code == 404
    assert client.get('/api/v1/monitoring').json()['event_count'] == 0
    schema = client.get('/openapi.json').json()
    assert '/api/v1/predictions' in schema['paths']


def test_auth_cors_and_identity(settings):
    settings = replace(settings, mode='authenticated', credentials={'analyst':'k'*32}, allowed_origins=('https://example.test',))
    with TestClient(create_app(settings)) as c:
        assert c.get('/health/live').status_code == 200
        for path in ('/api/v1/model','/docs','/openapi.json'):
            assert c.get(path).status_code == 401
        assert c.post('/api/v1/predictions', content='x'*70000).status_code == 401
        assert c.get('/api/v1/model', headers={'X-API-Key':'wrong'}).status_code == 401
        headers = {'Authorization':'Bearer '+'k'*32}
        prediction = c.post('/api/v1/predictions', headers=headers, json={'text':'The office opens tomorrow.', 'event_id':'a'}).json()
        cid = prediction['cluster_id_or_null']
        assert cid is not None
        response = c.post(f'/api/v1/clusters/{cid}/reviews', headers=headers, json={'review_id':'r','status':'rejected'})
        assert response.json()['actor'] == 'analyst'
        assert response.json()['actor_verified'] is True
        assert c.post(f'/api/v1/clusters/{cid}/reviews', headers=headers,
                      json={'review_id':'s','status':'pending','actor':'spoof'}).status_code == 422
        preflight = c.options('/api/v1/predictions', headers={'Origin':'https://example.test','Access-Control-Request-Method':'POST'})
        assert preflight.headers['access-control-allow-origin'] == 'https://example.test'
        assert 'access-control-allow-origin' not in c.get('/health/live', headers={'Origin':'https://evil.test'}).headers


def test_fail_closed_settings():
    with pytest.raises(ValueError):
        Settings(mode='authenticated')
    with pytest.raises(ValueError):
        Settings(credentials={'a':'short'})


def test_stream_limit_and_auth_before_receive(settings):
    from svo_api.auth import Boundary
    called = []

    async def inner(scope, receive, send):
        called.append(True)

    async def run(auth):
        output, reads = [], []
        async def receive():
            reads.append(1)
            return {'type':'http.request','body':b'x'*40000,'more_body':True}
        async def send(message):
            output.append(message)
        scope = {'type':'http','method':'POST','path':'/api/v1/predictions',
                 'headers':[(b'content-type',b'application/json')]}
        config = replace(settings, mode='authenticated', credentials={'a':'k'*32}) if auth else settings
        await Boundary(inner, config)(scope, receive, send)
        return output[0]['status'], reads
    status, reads = asyncio.run(run(False))
    assert status == 413 and len(reads) == 2
    status, reads = asyncio.run(run(True))
    assert status == 401 and not reads
    assert not called
