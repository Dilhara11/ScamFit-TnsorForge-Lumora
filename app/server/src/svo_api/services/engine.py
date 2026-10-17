import asyncio
from concurrent.futures import Future
import fcntl
import hashlib
import logging
from pathlib import Path
import queue
import sqlite3
import threading

import svo
from svo.artifacts import verify_bundle
from svo.model import Runtime
from svo_api.errors import APIError
from svo_api.services.monitoring import DurableMonitor

LOG = logging.getLogger('svo_api')
MODULES = ('__init__.py', 'model.py', 'monitor.py', 'preprocessing.py', 'artifacts.py', 'data.py')


def verify_runtime(settings):
    manifest = verify_bundle(settings.model_dir)
    if manifest['version'] != settings.expected_version or manifest['candidate'] != 'tfidf':
        raise ValueError('Unexpected model version or representation')
    source = Path(svo.__file__).parent
    for name in MODULES:
        digest = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if digest != manifest['source_hashes'].get(f'src/svo/{name}'):
            raise ValueError('Frozen runtime source mismatch')
    return manifest


class Engine:
    """Only this thread touches the Runtime and SQLite connection."""

    def __init__(self, settings):
        self.settings = settings
        self.queue = queue.Queue(maxsize=settings.queue_capacity)
        self.ready = False
        self.accepting = False
        self.stopping = threading.Event()
        self.started = Future()
        self.thread = threading.Thread(target=self._run, name='svo-engine', daemon=True)
        self.monitor = None

    async def start(self):
        self.thread.start()
        await asyncio.wrap_future(self.started)
        self.accepting = True

    def _run(self):
        lock = None
        try:
            verify_runtime(self.settings)
            self.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            lock = open(str(self.settings.db_path) + '.lock', 'a')
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            runtime = Runtime(self.settings.model_dir)
            runtime.predict('Service startup check.')
            self.monitor = DurableMonitor(runtime, self.settings)
            self.metadata = {
                'model_version': runtime.version, 'reference_version': runtime.version,
                'representation': 'tfidf', 'scope': runtime.config['scope'],
                'scores_calibrated': False, 'mode': self.settings.mode,
                'decision_config': runtime.config,
                'limitations': ['Unreviewed demonstration; not validated fraud protection.',
                                'Scores are uncalibrated; novelty is lexical, not fraud probability.',
                                'Low risk is not proof of safety.',
                                'Held-out high-risk recall: 69.4%; review workload: 100%.',
                                'Normal replay false-alert windows: 11.1%; no candidate cluster at replay end.'],
            }
            self.ready = True
            self.started.set_result(None)
            while not self.stopping.is_set() or not self.queue.empty():
                try:
                    future, method, args = self.queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    if not self.ready:
                        raise APIError(503, 'engine_unavailable', 'Restart required after storage failure')
                    result = getattr(self.monitor, method)(*args)
                    future.set_result(result)
                except (sqlite3.Error, OSError):
                    self.ready = False
                    try:
                        self.monitor.db.rollback()
                    except sqlite3.Error:
                        pass
                    future.set_exception(APIError(503, 'storage_unavailable', 'Storage is unavailable; restart after repair'))
                except Exception as exc:
                    future.set_exception(exc)
                finally:
                    self.queue.task_done()
        except Exception:
            self.ready = False
            if not self.started.done():
                self.started.set_exception(RuntimeError('Engine startup failed: check bundle, source, storage, and single-worker configuration'))
            LOG.error('engine_startup_failed')  # no payloads, paths or secrets
        finally:
            self.ready = False
            if self.monitor is not None:
                self.monitor.close()
            if lock is not None:
                lock.close()

    async def call(self, method, *args):
        if not self.ready or not self.accepting:
            raise APIError(503, 'engine_unavailable', 'Engine is not ready')
        future = Future()
        try:
            self.queue.put_nowait((future, method, args))
        except queue.Full:
            raise APIError(429, 'queue_full', 'Engine queue is full; retry with the same ID', {'Retry-After': '1'}) from None
        wrapped = asyncio.wrap_future(future)
        # Observe failures even when a disconnected caller no longer awaits the result.
        wrapped.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        return await asyncio.shield(wrapped)

    async def close(self):
        self.accepting = False
        self.stopping.set()
        await asyncio.to_thread(self.thread.join, self.settings.shutdown_seconds)
        self.ready = False
        if self.thread.is_alive():
            LOG.error('engine_drain_timeout')
