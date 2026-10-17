"""Durable, bounded novelty clusters and rolling drift. Logs contain no raw text."""
import json
import sqlite3
import time
from pathlib import Path

import numpy as np

from .preprocessing import text_hash


class Monitor:
    def __init__(self, runtime, db):
        self.runtime = runtime
        self.config = runtime.config
        Path(db).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE, text_hash TEXT,
              version TEXT, created REAL, prediction TEXT);
            CREATE TABLE IF NOT EXISTS windows (
              seq INTEGER PRIMARY KEY, version TEXT, unknown_fraction REAL,
              review_fraction REAL, score_mean REAL, elevated INTEGER, alert INTEGER);
            CREATE TABLE IF NOT EXISTS clusters (
              id INTEGER PRIMARY KEY, version TEXT, centroid BLOB, hashes TEXT,
              reports INTEGER, first_seq INTEGER, last_seq INTEGER, status TEXT,
              novelty_sum REAL);
            CREATE TABLE IF NOT EXISTS reviews (
              id INTEGER PRIMARY KEY, cluster_id INTEGER, status TEXT, actor TEXT,
              created REAL, version TEXT);
        ''')
        self.db.commit()

    def close(self):
        self.db.close()

    def process(self, text, event_id):
        h = text_hash(text)
        existing = self.db.execute("SELECT prediction,text_hash,version FROM events WHERE event_id=?", (event_id,)).fetchone()
        if existing:
            if existing[1] != h or existing[2] != self.runtime.version:
                raise ValueError("event_id already used for different text or model version")
            return json.loads(existing[0])
        predictions, x = self.runtime.predict_vectors([text])
        result = predictions[0]
        version = self.runtime.version
        seq = self.db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM events").fetchone()[0]
        if result["needs_review"]:
            z = x.toarray()[0] if hasattr(x, "toarray") else np.asarray(x[0])
            z = np.asarray(z, dtype=np.float32)
            clusters = self.db.execute("SELECT id,centroid,hashes,reports,novelty_sum,status FROM clusters WHERE version=?", (version,)).fetchall()
            best, similarity = None, -1.0
            for c in clusters:
                dot = float(np.dot(z, np.frombuffer(c[1], dtype=np.float32)))
                if dot > similarity:
                    best, similarity = c, dot
            if best is not None and similarity >= self.config["cluster_similarity"]:
                cid, blob, hashes, reports, novelty_sum, status = best
                hashes = set(json.loads(hashes))
                # Duplicates increase volume but never change centroid/unique recurrence.
                if h not in hashes:
                    centroid = np.frombuffer(blob, dtype=np.float32).copy() * len(hashes) + z
                    centroid /= max(float(np.linalg.norm(centroid)), 1e-12)
                    hashes.add(h)
                    # Bound stored distinct hashes; recurrence only needs a small count.
                    hashes = set(sorted(hashes)[:1000])
                    blob = centroid.astype(np.float32).tobytes()
                self.db.execute("UPDATE clusters SET centroid=?, hashes=?, reports=?, last_seq=?, novelty_sum=? WHERE id=?",
                    (blob, json.dumps(sorted(hashes)), reports + 1, seq, novelty_sum + result["novelty_score"], cid))
            else:
                if len(clusters) >= self.config["max_clusters"]:
                    # Keep unreviewed evidence durable; reject new clustering when full.
                    result["cluster_capacity_reached"] = True
                    cid = None
                else:
                    cursor = self.db.execute("INSERT INTO clusters(version,centroid,hashes,reports,first_seq,last_seq,status,novelty_sum) VALUES (?,?,?,?,?,?,?,?)",
                        (version, z.tobytes(), json.dumps([h]), 1, seq, seq, "pending", result["novelty_score"]))
                    cid = cursor.lastrowid
            result["cluster_id_or_null"] = cid
        self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
            (seq, event_id, h, version, time.time(), json.dumps(result)))
        count = self.db.execute("SELECT COUNT(*) FROM events WHERE version=?", (version,)).fetchone()[0]
        window_size = self.config["window_size"]
        if count >= window_size and (count-window_size) % self.config["window_stride"] == 0:
            recent = [json.loads(r[0]) for r in self.db.execute(
                "SELECT prediction FROM events WHERE version=? ORDER BY seq DESC LIMIT ?", (version, window_size))]
            unknown = float(np.mean([r["is_unknown"] for r in recent]))
            review = float(np.mean([r["needs_review"] for r in recent]))
            elevated = unknown > self.config["drift_unknown_threshold"]
            previous = self.db.execute("SELECT elevated FROM windows WHERE version=? ORDER BY seq DESC LIMIT ?",
                (version, self.config["consecutive_windows"] - 1)).fetchall()
            alert = bool(elevated and len(previous) == self.config["consecutive_windows"] - 1 and all(r[0] for r in previous))
            self.db.execute("INSERT INTO windows VALUES (?,?,?,?,?,?,?)", (seq, version, unknown, review,
                float(np.mean([r["scam_score"] for r in recent])), int(elevated), int(alert)))
        self.db.commit()
        return result

    def queue(self):
        rows = self.db.execute("SELECT id,hashes,reports,first_seq,last_seq,status,novelty_sum FROM clusters WHERE version=?", (self.runtime.version,)).fetchall()
        return [{"cluster_id": r[0], "unique_text_count": len(json.loads(r[1])), "report_count": r[2],
                 "first_seq": r[3], "last_seq": r[4], "status": r[5],
                 "mean_novelty": r[6]/r[2], "candidate_variant":
                 len(json.loads(r[1])) >= self.config["min_cluster_unique"] and
                 r[6]/r[2] > self.config["novelty_threshold"],
                 "model_version": self.runtime.version} for r in rows]

    def review(self, cluster_id, status, actor):
        if status not in ("confirmed", "rejected", "pending") or not actor.strip():
            raise ValueError("status must be confirmed/rejected/pending and actor must be provided")
        cursor = self.db.execute("UPDATE clusters SET status=? WHERE id=? AND version=?",
                                 (status, cluster_id, self.runtime.version))
        if cursor.rowcount != 1:
            raise ValueError("Unknown cluster for this model version")
        self.db.execute("INSERT INTO reviews(cluster_id,status,actor,created,version) VALUES (?,?,?,?,?)",
                        (cluster_id, status, actor, time.time(), self.runtime.version))
        self.db.commit()
        return {"cluster_id": cluster_id, "status": status, "automatic_retraining": False}

    def status(self):
        row = self.db.execute("SELECT seq,unknown_fraction,review_fraction,score_mean,alert FROM windows WHERE version=? ORDER BY seq DESC LIMIT 1", (self.runtime.version,)).fetchone()
        return {"model_version": self.runtime.version,
                "monitoring": "insufficient observations" if row is None else "ready",
                "latest_window": None if row is None else dict(zip(
                    ["end_seq", "unknown_fraction", "review_fraction", "score_mean", "alert"], row)),
                "queue": self.queue()}
