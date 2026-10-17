import pickle
import unittest

import numpy as np

from svo.train_v2 import folds, high_threshold, low_threshold
from svo.v2 import CalibratedHead, Features2, canonical, duplicate_weights

CONFIG = {"min_df": 1, "max_features": 5000, "precision_target": .9, "recall_target": .8,
          "low_risk_max_scam_leak": .1}


def row(i, label, group, language="en", synthetic=True, text=None):
    return {"id": str(i), "text": text or f"message {i}", "label": label, "language": language,
            "scenario_group_id": group, "synthetic": synthetic, "source_type": "synthetic"}


class V2Tests(unittest.TestCase):
    def test_masking_is_source_independent(self):
        # v1: the CSV text carried mask tokens, the identical raw text did not.
        imported = "[NAME_OR_WORD] customer, pay Rs [NUMBER] by <DATE_TIME> at <URL>"
        raw = "Dear customer, pay Rs 4500 by 12/10/2026 at http://pay.example.lk/x"
        self.assertEqual(canonical(imported), canonical(raw))
        self.assertEqual(canonical(canonical(raw)), canonical(raw))
        self.assertIn("ඔබගේ", canonical("ඔබගේ ගිණුම 1234"))

    def test_prefix_copies_share_weight_and_classes_balance(self):
        rows = [row(0, "scam", "g1"), row(1, "scam", "g1"), row(2, "legitimate", "g2"),
                row(3, "legitimate", "g3"), row(4, "legitimate", "g4")]
        w = duplicate_weights(rows)
        self.assertAlmostEqual(w[0], w[1])
        self.assertAlmostEqual(w[:2].sum(), w[2:].sum())

    def test_grouped_folds_never_split_a_scenario(self):
        rows = [row(i, "scam" if i % 2 else "legitimate", f"g{i // 4}") for i in range(80)]
        for tr, va in folds(rows, 5, 0):
            self.assertFalse({rows[i]["scenario_group_id"] for i in tr} & {rows[i]["scenario_group_id"] for i in va})

    def test_thresholds_fail_closed_and_bound_scam_leak(self):
        rows = [row(i, "scam" if i < 10 else "legitimate", f"g{i}") for i in range(20)]
        scores = np.r_[np.linspace(.6, .99, 10), np.linspace(.01, .7, 10)]
        high, met, _ = high_threshold(rows, scores, CONFIG)
        self.assertLess(high, 1.01)
        low = low_threshold(rows, scores, CONFIG, high)
        self.assertLessEqual(np.mean(scores[:10] < low), CONFIG["low_risk_max_scam_leak"])
        self.assertLessEqual(low, high)
        _, met, _ = high_threshold(rows, np.r_[np.zeros(10), np.ones(10)], CONFIG)
        self.assertFalse(met)

    def test_tfidf_features_are_unit_norm_and_head_round_trips(self):
        texts = ["Send the OTP now to keep your account", "Lunch at noon?", "Pay the parcel fee today",
                 "Meeting moved to Friday", "Verify your bank login here", "See you at home"]
        rows = [row(i, "scam" if i % 2 == 0 else "legitimate", f"g{i}", text=t) for i, t in enumerate(texts)]
        for variant in ("tfidf_char", "tfidf_union"):
            f = Features2(variant, CONFIG)
            x = f.fit(texts)
            self.assertTrue(np.allclose(np.sqrt(x.multiply(x).sum(axis=1)), 1, atol=1e-5))
            head = CalibratedHead(1.0).fit(x, rows)
            head.set_calibration(head.raw(x), rows)
            copy = pickle.loads(pickle.dumps((f, head)))
            self.assertTrue(np.allclose(copy[1].predict_proba(copy[0].transform(texts)), head.predict_proba(x)))


if __name__ == "__main__":
    unittest.main()
