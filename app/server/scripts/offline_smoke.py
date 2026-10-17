"""Run inside an isolated --network none container with writable /data and /tmp."""
import json
import subprocess
import sys
import time
import urllib.request
from smoke import run

start = time.monotonic()
process = subprocess.Popen([sys.executable, '-m', 'svo_api'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError('API exited during startup')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=.5):
                break
        except OSError:
            time.sleep(.2)
    else:
        raise RuntimeError('Readiness timed out')
    elapsed = time.monotonic() - start
    print(json.dumps({**run('http://127.0.0.1:8000'), 'startup_seconds':round(elapsed,3), 'network':'none'}))
finally:
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
