import json
import io
import tempfile
import unittest
from pathlib import Path

import numpy as np

from svo.artifacts import seal_bundle, verify_bundle
from svo.data import load_data
from svo.monitor import Monitor
from svo.preprocessing import normalize
from svo.serve import make_handler


class FakeRuntime:
    version = "test-version"
    config = {"window_size": 3, "window_stride": 1, "consecutive_windows": 2,
              "drift_unknown_threshold": .5, "cluster_similarity": .8,
              "max_clusters": 4, "min_cluster_unique": 3, "novelty_threshold": .5}

    def predict_vectors(self, texts):
        return [{"scam_score": .01, "decision": "review", "is_unknown": True,
            "needs_review": True, "novelty_score": .9, "cluster_id_or_null": None,
            "model_version": self.version} for _ in texts], np.tile([1., 0.], (len(texts), 1))


class PipelineTests(unittest.TestCase):
    def test_http_handler_validation_without_network(self):
        class RequestStream:
            def __init__(self, raw):
                self.input = io.BytesIO(raw)
                self.output = io.BytesIO()
            def makefile(self, mode, *args):
                return self.input
            def sendall(self, data):
                self.output.write(data)
        runtime = FakeRuntime()
        runtime.config['scope'] = 'test'
        with tempfile.TemporaryDirectory() as tmp:
            monitor = Monitor(runtime, Path(tmp)/'http.sqlite')
            handler = make_handler(runtime, monitor)
            def request(path, body):
                payload = json.dumps(body).encode()
                stream = RequestStream(b'POST ' + path.encode() + b' HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(payload)).encode() + b'\r\n\r\n' + payload)
                handler(stream, ('127.0.0.1', 1), object())
                return stream.output.getvalue()
            self.assertIn(b'200 OK', request('/predict', {'text':'Test notice', 'event_id':'test'}))
            self.assertIn(b'400 Bad Request', request('/predict', {'text':' '}))
            self.assertIn(b'400 Bad Request', request('/predict', {'text':12}))
            self.assertIn(b'400 Bad Request', request('/predict', {'text':'Other notice', 'event_id':'test'}))
            self.assertIn(b'200 OK', request('/review', {'cluster_id':1, 'status':'rejected', 'actor':'tester'}))
            self.assertIn(b'404 Not Found', request('/missing', {}))
            monitor.close()

    def test_normalization_preserves_scripts_and_rejects_empty(self):
        self.assertEqual(normalize(" සිංහල\n தமிழ்  "), "සිංහල தமிழ்")
        self.assertEqual(normalize("e\u0301"), "é")
        with self.assertRaises(ValueError): normalize(" ")

    def test_duplicates_do_not_create_variant_and_restart_keeps_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "monitor.sqlite"
            m = Monitor(FakeRuntime(), path)
            for i in range(4): m.process("same fictional report", str(i))
            self.assertEqual(m.queue()[0]["unique_text_count"], 1)
            self.assertFalse(m.queue()[0]["candidate_variant"])
            self.assertEqual(m.status()["latest_window"]["alert"], 1)
            count = m.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            m.process("same fictional report", "0")
            self.assertEqual(m.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], count)
            with self.assertRaisesRegex(ValueError, "event_id already used"):
                m.process("different request", "0")
            m.close()
            m = Monitor(FakeRuntime(), path)
            m.process("different fictional report", "next")
            m.process("another fictional report", "last")
            self.assertTrue(m.queue()[0]["candidate_variant"])
            m.review(1, "rejected", "test-analyst")
            self.assertEqual(m.queue()[0]["status"], "rejected")
            self.assertEqual(m.db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0], 1)
            m.close()

    def test_bundle_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ("model.joblib", "decision_config.json", "model_card.md"):
                (p / name).write_text("original")
            seal_bundle(p, {"test": True})
            verify_bundle(p)
            (p / "model.joblib").write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_bundle(p)

    def test_cross_split_group_is_rejected(self):
        row = {"id": "1", "text": "Test record one", "label": "scam", "language": "en",
               "family": "test", "scenario_group_id": "shared", "source_id": "test",
               "source_type": "synthetic", "license_or_generation_method": "test fixture",
               "human_review_status": "unreviewed", "synthetic": True, "split": "train"}
        second = {**row, "id": "2", "text": "Test record two", "split": "test_id"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.jsonl"
            path.write_text(json.dumps(row) + "\n" + json.dumps(second))
            with self.assertRaisesRegex(ValueError, "Group leakage"):
                load_data(path, simulation=True)
            with self.assertRaisesRegex(ValueError, "Unreviewed"):
                load_data(path)


if __name__ == "__main__":
    unittest.main()
