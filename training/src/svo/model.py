import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             f1_score, precision_score, recall_score)

from .preprocessing import normalize


class Features:
    def __init__(self, kind, config, encoder_path=None):
        self.kind = kind
        self.config = config
        self.encoder_path = encoder_path
        self.vectorizer = None
        self.encoder = None

    def fit(self, texts):
        if self.kind == "tfidf":
            self.vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(3, 5),
                min_df=self.config["min_df"], max_features=self.config["max_features"],
                sublinear_tf=True, dtype=np.float32)
            return self.vectorizer.fit_transform([normalize(t) for t in texts])
        return self.transform(texts)

    def transform(self, texts):
        texts = [normalize(t) for t in texts]
        if self.kind == "tfidf":
            return self.vectorizer.transform(texts)
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer(str(self.encoder_path), device="cpu", local_files_only=True)
            self.encoder.max_seq_length = self.config["max_length"]
        return self.encoder.encode(["query: " + t for t in texts],
            batch_size=self.config["embedding_batch_size"], normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False)


def fit_head(x, rows, c):
    y = np.array([r["label"] == "scam" for r in rows], dtype=int)
    return LogisticRegression(C=c, class_weight="balanced", max_iter=1000,
                              random_state=42).fit(x, y)


def metrics(rows, scores, threshold=0.5):
    y = np.array([r["label"] == "scam" for r in rows], dtype=int)
    pred = np.asarray(scores) >= threshold
    return {"n": len(rows), "groups": len({r["scenario_group_id"] for r in rows}),
        "scam_count": int(y.sum()), "legitimate_count": int((1-y).sum()),
        "macro_f1": float(f1_score(y, pred, average="macro", labels=[0, 1], zero_division=0)),
        "scam_precision": float(precision_score(y, pred, zero_division=0)),
        "scam_recall": float(recall_score(y, pred, zero_division=0)),
        "scam_f1": float(f1_score(y, pred, zero_division=0)),
        "pr_auc_average_precision": float(average_precision_score(y, scores)) if y.sum() else None,
        "brier": float(brier_score_loss(y, scores)),
        "confusion_matrix_legitimate_scam": confusion_matrix(y, pred, labels=[0, 1]).tolist(),
        "high_risk_false_positive_rate": float(pred[y == 0].mean()) if (y == 0).any() else None}


def select_threshold(rows, scores, config):
    candidates = []
    for t in np.unique(np.r_[0.5, scores]):
        m = metrics(rows, scores, float(t))
        if m["scam_precision"] >= config["precision_target"] and m["scam_recall"] >= config["recall_target"]:
            candidates.append((m["scam_recall"], m["scam_precision"], float(t)))
    if not candidates:
        return 1.01, False  # fail closed: no automatic high-risk assertion
    return max(candidates)[2], True


class Runtime:
    def __init__(self, bundle, verify=True):
        from .artifacts import verify_bundle
        self.bundle = Path(bundle)
        self.manifest = verify_bundle(bundle) if verify else json.loads((self.bundle / "manifest.json").read_text())
        self.version = self.manifest["version"]
        self.config = json.loads((self.bundle / "decision_config.json").read_text())
        payload = joblib.load(self.bundle / "model.joblib")
        self.features, self.head, self.reference, self.metadata = (
            payload[k] for k in ("features", "head", "reference", "metadata"))
        if self.features.kind == "e5":
            self.features.encoder_path = self.bundle / "encoder"
            self.features.encoder = None

    def predict_vectors(self, texts):
        x = self.features.transform(texts)
        scores = self.head.predict_proba(x)[:, 1]
        similarities = x @ self.reference.T
        if hasattr(similarities, "toarray"):
            similarities = similarities.toarray()
        similarities = np.clip(np.asarray(similarities), -1, 1)
        out = []
        scam_indices = [i for i, r in enumerate(self.metadata) if r.get("label") == "scam"]
        for i, score in enumerate(scores):
            nearest = int(similarities[i].argmax())
            novelty = float(1 - similarities[i, nearest])
            unknown = novelty > self.config["novelty_threshold"]
            decision = "high_risk" if score >= self.config["high_risk_threshold"] else (
                "low_risk" if score < self.config["low_risk_threshold"] and not unknown else "review")
            nearest_scam = scam_indices[int(similarities[i, scam_indices].argmax())] if scam_indices else None
            out.append({"scam_score": float(score), "decision": decision,
                "needs_review": bool(unknown or decision != "low_risk"),
                "novelty_score": novelty, "is_unknown": bool(unknown),
                "nearest_known_family_or_null": self.metadata[nearest_scam]["family"] if not unknown and nearest_scam is not None else None,
                "cluster_id_or_null": None, "model_version": self.version,
                "reference_version": self.version,
                "scope": self.config["scope"]})
        return out, x

    def predict(self, text):
        return self.predict_vectors([text])[0][0]
