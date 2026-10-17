import asyncio
from concurrent.futures import Future
import hashlib
import json
import logging
from pathlib import Path
import queue
import sqlite3
import threading

import svo
from svo.model import Runtime
from svo_api.errors import APIError
from svo_api.services.monitoring import DurableMonitor

try:
    import fcntl
except ImportError:  # Windows development host; the container uses fcntl
    fcntl = None
    import msvcrt

LOG = logging.getLogger('svo_api')
MODULES = ('__init__.py', 'model.py', 'monitor.py', 'preprocessing.py', 'artifacts.py', 'data.py')
# Servable representations -> extra runtime modules they unpickle. `tfidf_char_raw`
# is the v2 shortcut ablation (no shared masking) and is never servable.
REPRESENTATIONS = {
    'tfidf': (),  # v1
    'tfidf_char': ('v2.py',), 'tfidf_union': ('v2.py',),
    'e5': ('v2.py',), 'e5_tfidf': ('v2.py',),
}
# Held-out evidence per frozen version (training/RESULTS*.md); shown by GET /api/v1/model.
EVIDENCE = {
    'svo-38879254a924': ['Scores are uncalibrated; novelty is lexical, not fraud probability.',
                         'Held-out high-risk recall: 69.4%; review workload: 100%.',
                         'Normal replay false-alert windows: 11.1%; no candidate cluster at replay end.'],
    'svo-e2a46f504b19': ['Scores are Platt-calibrated under a balanced class prior, not deployment prevalence.',
                         'Held-out macro-F1 0.932; high-risk precision 83.2% (target 90% not met), recall 98.8%.',
                         'Legitimate false-positive rate 9.8%, mostly formal synthetic notices; real SMS 1.4%.',
                         'Drift: the held-out shift was not detected; novelty is not a fraud signal.'],
}


def verify_bundle_portable(bundle):
    """svo.artifacts.verify_bundle, but tolerant of bundles sealed on Windows, whose
    manifest keys use backslashes. Same version and hash checks; paths stay inside."""
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / 'manifest.json').read_text())
    unsigned = {k: v for k, v in manifest.items() if k != 'version'}
    expected = 'svo-' + hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest()[:12]
    if manifest['version'] != expected:
        raise ValueError('Manifest content/version mismatch')
    files = {name.replace('\\', '/'): checksum for name, checksum in manifest['files'].items()}
    if not {'model.joblib', 'decision_config.json', 'model_card.md'} <= files.keys():
        raise ValueError('Incomplete artifact manifest')
    for name, checksum in files.items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle) or not path.is_file() \
                or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError('Artifact hash mismatch/missing file')
    return manifest


def verify_runtime(settings):
    manifest = verify_bundle_portable(settings.model_dir)
    if manifest['version'] != settings.expected_version or manifest['candidate'] not in REPRESENTATIONS:
        raise ValueError('Unexpected model version or representation')
    source = Path(svo.__file__).parent
    for name in MODULES + REPRESENTATIONS[manifest['candidate']]:
        path = source / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if digest != manifest['source_hashes'].get(f'src/svo/{name}'):
            raise ValueError('Frozen runtime source mismatch')
    return manifest


def load_runtime(settings):
    """Verify artifact and source identity before any joblib load, then load once."""
    manifest = verify_runtime(settings)
    return Runtime(settings.model_dir, verify=False), manifest


def lock_exclusive(handle):
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    else:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)


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
            self.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
            lock = open(str(self.settings.db_path) + '.lock', 'a')
            lock_exclusive(lock)
            runtime, manifest = load_runtime(self.settings)
            runtime.predict('Service startup check.')
            self.monitor = DurableMonitor(runtime, self.settings)
            self.metadata = {
                'model_version': runtime.version, 'reference_version': runtime.version,
                'representation': manifest['candidate'], 'scope': runtime.config['scope'],
                'scores_calibrated': bool(runtime.config.get('scores_calibrated', False)),
                'mode': self.settings.mode,
                'decision_config': runtime.config,
                'limitations': ['Unreviewed demonstration; not validated fraud protection.',
                                'Low risk is not proof of safety.',
                                *EVIDENCE.get(runtime.version, ['No held-out evidence recorded for this version.'])],
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
