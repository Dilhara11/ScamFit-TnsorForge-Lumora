import hashlib
import json
import shutil
import time

from svo.monitor import Monitor
from svo.preprocessing import text_hash
from svo_api.errors import APIError
from svo_api.schemas import Prediction, ReviewResult
from svo_api.storage.migrations import SCHEMA_VERSION, migrate


class DurableMonitor(Monitor):
    """Keep frozen scoring/window rules; add rollback and transactional review IDs."""

    def __init__(self, runtime, settings):
        super().__init__(runtime, settings.db_path)
        self.settings = settings
        try:
            migrate(self.db)
            self.check_storage()
        except Exception:
            self.close()
            raise

    def check_storage(self):
        free = shutil.disk_usage(self.settings.db_path.parent).free
        if free < self.settings.min_free_bytes:
            raise OSError('Storage reserve exhausted')
        return free

    def predict(self, request):
        self.check_storage()
        h = text_hash(request.text)
        row = self.db.execute('SELECT text_hash,version FROM events WHERE event_id=?',
                              (request.event_id,)).fetchone()
        if row and row != (h, self.runtime.version):
            raise APIError(409, 'event_conflict', 'Event ID belongs to another input or model version')
        try:
            result = self.process(request.text, request.event_id)
            return Prediction(event_id=request.event_id, **result).model_dump()
        except Exception:
            self.db.rollback()
            raise

    def cluster(self, cluster_id):
        for item in self.queue():
            if item['cluster_id'] == cluster_id:
                return item
        raise APIError(404, 'cluster_not_found', 'Cluster does not exist for this model version')

    def detail(self, cluster_id):
        item = self.cluster(cluster_id)
        rows = self.db.execute(
            "SELECT event_id FROM events WHERE version=? "
            "AND json_extract(prediction,'$.cluster_id_or_null')=? ORDER BY seq LIMIT 5",
            (self.runtime.version, cluster_id)).fetchall()
        return {**item, 'representative_event_ids': [r[0] for r in rows]}

    def clusters(self, status, limit, after_id):
        rows = sorted((r for r in self.queue() if r['cluster_id'] > after_id
                       and (status is None or r['status'] == status)), key=lambda r: r['cluster_id'])
        return {'items': rows[:limit],
                'next_after_id': rows[limit-1]['cluster_id'] if len(rows) > limit else None}

    def monitoring(self):
        current = self.status()
        queue = current.pop('queue')
        if current['latest_window'] is not None:
            current['latest_window']['alert'] = bool(current['latest_window']['alert'])
        return {**current,
                'event_count': self.db.execute('SELECT COUNT(*) FROM events WHERE version=?',
                                              (self.runtime.version,)).fetchone()[0],
                'cluster_count': len(queue),
                'pending_count': sum(r['status'] == 'pending' for r in queue),
                'candidate_count': sum(r['candidate_variant'] for r in queue),
                'disk_free_bytes': self.check_storage(), 'schema_version': SCHEMA_VERSION}

    def submit_review(self, cluster_id, request, actor, verified):
        self.check_storage()
        fingerprint = hashlib.sha256(json.dumps(
            [cluster_id, request.status, actor, verified, self.runtime.version]).encode()).hexdigest()
        previous = self.db.execute('SELECT fingerprint,response FROM review_requests WHERE review_id=?',
                                   (request.review_id,)).fetchone()
        if previous:
            if previous[0] != fingerprint:
                raise APIError(409, 'review_conflict', 'Review ID belongs to another review')
            return json.loads(previous[1])
        self.cluster(cluster_id)
        result = ReviewResult(review_id=request.review_id, cluster_id=cluster_id,
                              status=request.status, actor=actor, actor_verified=verified,
                              model_version=self.runtime.version).model_dump()
        with self.db:
            self.db.execute('UPDATE clusters SET status=? WHERE id=? AND version=?',
                            (request.status, cluster_id, self.runtime.version))
            cursor = self.db.execute('INSERT INTO reviews(cluster_id,status,actor,created,version) VALUES (?,?,?,?,?)',
                                    (cluster_id, request.status, actor, time.time(), self.runtime.version))
            self.db.execute('INSERT INTO review_requests VALUES (?,?,?,?)',
                            (request.review_id, fingerprint, cursor.lastrowid, json.dumps(result)))
        return result

    def reviews(self, cluster_id, limit, after_id):
        self.cluster(cluster_id)
        rows = self.db.execute(
            'SELECT r.id,r.cluster_id,r.status,r.actor,r.created,r.version,q.review_id,q.response '
            'FROM reviews r LEFT JOIN review_requests q ON q.audit_id=r.id '
            'WHERE r.version=? AND r.cluster_id=? AND r.id>? ORDER BY r.id LIMIT ?',
            (self.runtime.version, cluster_id, after_id, limit+1)).fetchall()
        items = [dict(zip(['id','cluster_id','status','actor','created','model_version','review_id'], r[:7]),
                      actor_verified=bool(json.loads(r[7])['actor_verified']) if r[7] else False)
                 for r in rows[:limit]]
        return {'items': items, 'next_after_id': items[-1]['id'] if len(rows) > limit else None}
