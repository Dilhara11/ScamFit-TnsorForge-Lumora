import json
from pathlib import Path
import shutil
import pytest
from svo.monitor import Monitor
from svo_api.services.engine import load_runtime, verify_runtime
from dataclasses import replace

TEXTS = ['The office opens tomorrow.', 'හෙට කාර්යාලය විවෘතයි.', 'நாளை அலுவலகம் திறந்திருக்கும்.',
         'heta office eka open.', 'naalai office open.', 'Cafe\u0301   opens tomorrow.']


def test_frozen_prediction_and_monitor_parity(client, settings, tmp_path):
    baseline = Monitor(load_runtime(settings)[0], tmp_path/'baseline.sqlite')
    try:
        for i in range(35):
            text = TEXTS[i % len(TEXTS)]
            expected = baseline.process(text, f'e{i}')
            response = client.post('/api/v1/predictions', json={'text':text,'event_id':f'e{i}'})
            assert response.status_code == 200, response.text
            actual = response.json()
            for key, value in expected.items():
                assert actual[key] == value
        status = client.get('/api/v1/monitoring').json()
        assert status['latest_window'] == baseline.status()['latest_window']
        assert client.get('/api/v1/clusters?limit=100').json()['items'] == baseline.queue()
    finally:
        baseline.close()


def test_private_shift_replay_parity(client, settings, tmp_path):
    data = Path(__file__).resolve().parents[3]/'training/data/processed/messages_v2.jsonl'
    if not data.exists():
        pytest.skip('Private replay input not supplied')
    rows = [json.loads(line) for line in data.read_text(encoding='utf-8').splitlines()]
    shifted = [r for r in rows if r['split'] == 'shift_demo']
    assert shifted
    baseline = Monitor(load_runtime(settings)[0], tmp_path/'replay.sqlite')
    try:
        for i, row in enumerate(shifted):
            expected = baseline.process(row['text'], f'shift-{i}')
            actual = client.post('/api/v1/predictions', json={'text':row['text'],'event_id':f'shift-{i}'}).json()
            assert {k:actual[k] for k in expected} == expected
        assert client.get('/api/v1/monitoring').json()['latest_window'] == baseline.status()['latest_window']
    finally:
        baseline.close()


def test_artifact_and_source_verification(settings, tmp_path, monkeypatch):
    assert verify_runtime(settings)['version'] == settings.expected_version
    with pytest.raises(ValueError):
        verify_runtime(replace(settings, expected_version='wrong'))
    target = tmp_path/'bundle'
    shutil.copytree(settings.model_dir, target)
    (target/'model.joblib').write_bytes(b'tampered')
    with pytest.raises(ValueError):
        verify_runtime(replace(settings, model_dir=target))
    (target/'model.joblib').unlink()
    with pytest.raises(ValueError):
        verify_runtime(replace(settings, model_dir=target))
    import svo_api.services.engine as engine
    source = tmp_path/'source'
    source.mkdir()
    (source/'__init__.py').write_text('wrong source')
    monkeypatch.setattr(engine.svo, '__file__', str(source/'__init__.py'))
    with pytest.raises(ValueError, match='source mismatch'):
        verify_runtime(settings)


def _seal(bundle, files):
    import hashlib
    for name, data in files.items():
        path = bundle / name.replace('\\', '/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    content = {'files': {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}, 'format_version': 1}
    content['version'] = 'svo-' + hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()[:12]
    (bundle / 'manifest.json').write_text(json.dumps(content))
    return content


def test_windows_sealed_manifest_and_traversal(tmp_path):
    from svo_api.services.engine import verify_bundle_portable
    base = {'model.joblib': b'm', 'decision_config.json': b'{}', 'model_card.md': b'c'}
    ok = tmp_path / 'ok'
    _seal(ok, {**base, 'encoder\\config.json': b'{}'})  # key as written by seal_bundle on Windows
    assert verify_bundle_portable(ok)['files']
    (ok / 'encoder/config.json').write_bytes(b'tampered')
    with pytest.raises(ValueError):
        verify_bundle_portable(ok)
    bad = tmp_path / 'bad' / 'bundle'
    _seal(bad, {**base, '..\\outside.txt': b'x'})
    with pytest.raises(ValueError):
        verify_bundle_portable(bad)


def test_representation_allowlist_and_v2_source(settings, monkeypatch):
    import svo_api.services.engine as engine
    manifest = engine.verify_bundle_portable(settings.model_dir)
    assert engine.REPRESENTATIONS[manifest['candidate']] == ('v2.py',)
    monkeypatch.setattr(engine, 'verify_bundle_portable', lambda _: {**manifest, 'candidate': 'tfidf_char_raw'})
    with pytest.raises(ValueError, match='representation'):
        verify_runtime(settings)
    monkeypatch.setattr(engine, 'verify_bundle_portable', lambda _: {
        **manifest, 'source_hashes': {**manifest['source_hashes'], 'src/svo/v2.py': 'other'}})
    with pytest.raises(ValueError, match='source mismatch'):
        verify_runtime(settings)
