"""Small real HTTP benchmark; records service latency, never model quality."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import platform
import statistics
import time
import urllib.request
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8000')
parser.add_argument('--samples', type=int, default=100)
parser.add_argument('--concurrency', type=int, default=4)
args = parser.parse_args()
run_id = uuid.uuid4().hex
headers = {'Content-Type':'application/json'}
if os.getenv('SVO_API_KEY'):
    headers['X-API-Key'] = os.environ['SVO_API_KEY']


def request(path, body=None):
    start = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(args.url+path, headers=headers,
            data=None if body is None else json.dumps(body).encode()), timeout=10) as response:
        data = json.load(response)
    return (time.perf_counter()-start)*1000, data


def predict(i):
    return request('/api/v1/predictions', {'text':'The office opens tomorrow.', 'event_id':f'bench-{run_id}-{i}'})[0]


def health(_):
    return request('/health/ready')[0]


request('/health/ready')
with ThreadPoolExecutor(max_workers=args.concurrency) as pool, ThreadPoolExecutor(max_workers=1) as probes:
    work = [pool.submit(predict, i) for i in range(args.samples)]
    probe_work = [probes.submit(health, i) for i in range(20)]
    latencies = [f.result() for f in work]
    probes_ms = [f.result() for f in probe_work]


def summary(values):
    return {'p50_ms':round(statistics.median(values),3),
            'p95_ms':round(sorted(values)[max(0, int(len(values)*.95)-1)],3),
            'max_ms':round(max(values),3)}


print(json.dumps({'samples':args.samples,'concurrency':args.concurrency,
                  'platform':platform.platform(),'model_version':request('/health/ready')[1]['model_version'],
                  'prediction_http':summary(latencies),'health_during_load':summary(probes_ms)}, indent=2))
