import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
import threading
import pytest
from fastapi.testclient import TestClient
from svo.model import Runtime
from svo_api.main import create_app
from svo_api.schemas import PredictionRequest, ReviewRequest
from svo_api.services.monitoring import DurableMonitor
from svo_api.services.engine import Engine
from svo_api.errors import APIError


def test_concurrent_idempotency_and_restart(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        body = {'text':'The office opens tomorrow.', 'event_id':'duplicate'}
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: c.post('/api/v1/predictions', json=body), range(8)))
        assert all(r.status_code == 200 for r in results)
        assert all(r.json() == results[0].json() for r in results)
        assert c.get('/api/v1/monitoring').json()['event_count'] == 1
        assert c.post('/api/v1/predictions',json={**body,'text':'Different.'}).status_code == 409
        assert c.post('/api/v1/predictions',json={**body,'text':'  The office   opens tomorrow. '}).status_code == 200
        cid = results[0].json()['cluster_id_or_null']
        review = {'review_id':'review1','status':'rejected','actor':'demo'}
        first = c.post(f'/api/v1/clusters/{cid}/reviews',json=review).json()
        assert c.post(f'/api/v1/clusters/{cid}/reviews',json=review).json() == first
        assert c.post(f'/api/v1/clusters/{cid}/reviews',json={**review,'status':'confirmed'}).status_code == 409
        assert len(c.get(f'/api/v1/clusters/{cid}/reviews').json()['items']) == 1
        assert c.get(f'/api/v1/clusters/{cid}').json()['representative_event_ids'] == ['duplicate']
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/v1/monitoring').json()['event_count'] == 1
        assert c.post('/api/v1/predictions',json=body).json() == results[0].json()
        assert c.get(f'/api/v1/clusters/{cid}').json()['status'] == 'rejected'
        assert c.post(f'/api/v1/clusters/{cid}/reviews',json=review).json() == first


def test_rollback_and_backup(settings, tmp_path):
    monitor = DurableMonitor(Runtime(settings.model_dir), settings)
    try:
        monitor.db.execute("CREATE TEMP TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'injected'); END")
        with pytest.raises(sqlite3.Error):
            monitor.predict(PredictionRequest(text='The office opens tomorrow.',event_id='failure'))
        assert monitor.db.execute('SELECT COUNT(*) FROM clusters').fetchone()[0] == 0
        monitor.db.execute('DROP TRIGGER fail_event')
        result = monitor.predict(PredictionRequest(text='The office opens tomorrow.',event_id='success'))
        cid = result['cluster_id_or_null']
        monitor.db.execute("CREATE TEMP TRIGGER fail_review BEFORE INSERT ON review_requests BEGIN SELECT RAISE(ABORT,'injected'); END")
        with pytest.raises(sqlite3.Error):
            monitor.submit_review(cid, ReviewRequest(review_id='r',status='rejected'),'demo',False)
        assert monitor.cluster(cid)['status'] == 'pending'
        assert monitor.db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 0
        monitor.db.execute('DROP TRIGGER fail_review')
        backup = tmp_path/'backup.sqlite'
        with sqlite3.connect(backup) as target:
            monitor.db.backup(target)
    finally:
        monitor.close()
    restored = DurableMonitor(Runtime(settings.model_dir), replace(settings,db_path=backup))
    try:
        assert restored.monitoring()['event_count'] == 1
        assert restored.predict(PredictionRequest(text='The office opens tomorrow.',event_id='success')) == result
        restored.runtime.version = 'new-version-test'
        assert restored.monitoring()['event_count'] == 0
        assert restored.queue() == []
        with pytest.raises(APIError) as error:
            restored.predict(PredictionRequest(text='The office opens tomorrow.',event_id='success'))
        assert error.value.status == 409
    finally:
        restored.close()


def test_queue_saturation_cancellation_and_shutdown(settings):
    async def scenario():
        engine = Engine(replace(settings,queue_capacity=1))
        await engine.start()
        entered, release = threading.Event(), threading.Event()
        original = engine.monitor.monitoring
        def blocked():
            entered.set()
            release.wait(5)
            return original()
        engine.monitor.monitoring = blocked
        first = asyncio.create_task(engine.call('monitoring'))
        await asyncio.to_thread(entered.wait, 3)
        second = asyncio.create_task(engine.call('predict',PredictionRequest(text='Tomorrow.',event_id='cancelled')))
        await asyncio.sleep(.02)
        try:
            with pytest.raises(APIError) as error:
                await engine.call('monitoring')
            assert error.value.status == 429
            second.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second
        finally:
            release.set()
        await first
        await engine.close()
        with sqlite3.connect(settings.db_path) as db:
            assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 1
    asyncio.run(scenario())


def test_storage_failure_disables_readiness(client):
    engine = client.app.state.engine
    def failure():
        raise OSError('disk failed')
    engine.monitor.check_storage = failure
    assert client.post('/api/v1/predictions',json={'text':'Tomorrow.','event_id':'a'}).status_code == 503
    assert client.get('/health/ready').status_code == 503
    assert client.get('/health/live').status_code == 200


def test_review_pagination_and_private_storage(client, settings):
    prediction = client.post('/api/v1/predictions', json={'text':'The office opens tomorrow.', 'event_id':'private-event'}).json()
    cid = prediction['cluster_id_or_null']
    for i, status in enumerate(('rejected','pending','confirmed')):
        assert client.post(f'/api/v1/clusters/{cid}/reviews',json={'review_id':f'r{i}','status':status}).status_code == 200
    first = client.get(f'/api/v1/clusters/{cid}/reviews?limit=2').json()
    second = client.get(f'/api/v1/clusters/{cid}/reviews?limit=2&after_id={first["next_after_id"]}').json()
    assert [r['status'] for r in first['items']+second['items']] == ['rejected','pending','confirmed']
    assert second['next_after_id'] is None
    assert client.get('/api/v1/clusters?status=pending').json()['items'] == []
    with sqlite3.connect(settings.db_path) as db:
        assert 'The office opens tomorrow.' not in '\n'.join(db.iterdump())


def test_single_process_ownership(settings):
    async def scenario():
        first, second = Engine(settings), Engine(settings)
        await first.start()
        try:
            with pytest.raises(RuntimeError, match='startup failed'):
                await second.start()
            assert first.ready
        finally:
            await second.close()
            await first.close()
    asyncio.run(scenario())
