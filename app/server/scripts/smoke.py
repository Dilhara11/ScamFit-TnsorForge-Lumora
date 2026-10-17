"""Real HTTP smoke check. Only fictional text; no fixture corpus required."""
import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid


def run(base, key=None, event_id=None):
    event_id = event_id or 'smoke-' + uuid.uuid4().hex
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['X-API-Key'] = key

    def call(path, body=None, expected=200):
        request = urllib.request.Request(base.rstrip('/')+path,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            assert response.status == expected, f'{path}: expected {expected}, got {response.status}'
            return json.load(response)

    start = time.perf_counter()
    ready = call('/health/ready')
    metadata = call('/api/v1/model')
    # Fictional scam pattern: v2 routes ordinary text to low risk, so a cluster
    # (needed for the review round-trip) requires a review-routed message.
    body = {'text': 'Your parcel is held. Pay the release fee at the link today to receive it.', 'event_id': event_id}
    prediction = call('/api/v1/predictions', body)
    assert call('/api/v1/predictions', body) == prediction
    assert prediction['model_version'] == ready['model_version'] == metadata['model_version']
    call('/api/v1/predictions', {**body, 'text': 'A different office schedule.'}, 409)
    call('/api/v1/predictions', {'text': '', 'event_id': event_id+'-bad'}, 422)
    monitoring = call('/api/v1/monitoring')
    cid = prediction['cluster_id_or_null']
    assert cid is not None
    call(f'/api/v1/clusters/{cid}')
    review = {'review_id': event_id+'-review', 'status': 'rejected'}
    result = call(f'/api/v1/clusters/{cid}/reviews', review)
    assert result['automatic_retraining'] is False
    assert call(f'/api/v1/clusters/{cid}/reviews', review) == result
    assert call(f'/api/v1/clusters/{cid}/reviews')['items']
    return {'passed': True, 'model_version': ready['model_version'], 'event_id': event_id,
            'event_count': monitoring['event_count'], 'elapsed_ms': round((time.perf_counter()-start)*1000, 2)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--event-id')
    args = parser.parse_args()
    print(json.dumps(run(args.url, os.getenv('SVO_API_KEY'), args.event_id)))
