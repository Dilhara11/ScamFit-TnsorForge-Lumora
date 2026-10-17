"""V2 features and heads. One masking pipeline is applied to every source at
training and inference, so masking artefacts can no longer identify the source.

V1 masked only the imported CSV (all scams): `[NAME_OR_WORD]`, `<DATE_TIME>`,
`<URL>` etc. occurred in scam rows only and became the top scam features.
"""
import re

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from .preprocessing import normalize

# Upstream (Presidio-style) placeholders found in the imported CSV.
_LINK = re.compile(r"<(?:URL|EMAIL_ADDRESS|IP_ADDRESS)>|\[(?:URL|EMAIL)\]")
_NUMBER = re.compile(r"<(?:DATE_TIME|PHONE_NUMBER|US_BANK_NUMBER|US_DRIVER_LICENSE|UK_NHS|"
                     r"MEDICAL_LICENSE|CREDIT_CARD|US_SSN|IBAN_CODE)>|\[NUMBER\]")
_ENTITY = re.compile(r"<[A-Z_]{2,30}>|\[(?:ENTITY|NAME_OR_WORD|REDACTED|[A-Z]{2,6})\]")


def scrub(text):
    """Same rules as scripts/prepare_data.py::scrub (without per-row entity lists)."""
    text = normalize(text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?i)(?:https?://|www\.)\S+|\b(?:[a-z0-9-]+\.)+(?:com|net|org|lk|io|xyz|co|me|uk|in|info|site|top|link|live|online|click|ly)\b\S*", "[URL]", text)
    text = re.sub(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b\S*", "[URL]", text)
    text = re.sub(r"\+?\d[\d\s()./-]{3,}\d", "[NUMBER]", text)
    text = re.sub(r"\d+", "[NUMBER]", text)
    text = re.sub(r"\b[A-Z][a-z]{2,}\b", "[NAME_OR_WORD]", text)
    return normalize(text)


def canonical(text):
    """Source-independent text: identical masking, then short neutral tokens."""
    text = scrub(text)
    text = _LINK.sub(" ‹link› ", text)
    text = _NUMBER.sub(" ‹num› ", text)
    text = _ENTITY.sub(" ‹ent› ", text)
    return normalize(text.lower())


def _tfidf_union(config):
    # Python \w excludes Sinhala/Tamil combining marks, so split on whitespace/punctuation.
    return [TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=config["min_df"],
                            max_features=config["max_features"], sublinear_tf=True, dtype=np.float32),
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=config["min_df"],
                            token_pattern=r"(?u)[^\s.,!?;:()\"'“”]+", sublinear_tf=True, dtype=np.float32)]


class Features2:
    """Variants: tfidf_char_raw (v1 ablation), tfidf_char (v1 features on canonical
    text), tfidf_union, e5, e5_tfidf.

    `kind` stays "tfidf"/"e5" so svo.model.Runtime attaches the bundled encoder.
    Every variant returns L2-normalised rows, so `x @ reference.T` is cosine.
    """

    def __init__(self, variant, config, encoder_path=None):
        self.variant = variant
        self.kind = "e5" if variant.startswith("e5") else "tfidf"
        self.config = config
        self.encoder_path = encoder_path
        self.encoder = None
        self.vectorizers = []
        self.embedding_cache = None  # training only; dropped before export

    def prepare(self, text):
        # tfidf_char_raw is the v1 ablation: no shared masking, shortcut left in place.
        return normalize(text) if self.variant == "tfidf_char_raw" else canonical(text)

    def fit(self, texts):
        texts = [self.prepare(t) for t in texts]
        if self.variant in ("tfidf_char", "tfidf_char_raw"):
            self.vectorizers = [TfidfVectorizer(analyzer="char", ngram_range=(3, 5),
                min_df=self.config["min_df"], max_features=self.config["max_features"],
                sublinear_tf=True, dtype=np.float32)]
        elif self.variant in ("tfidf_union", "e5_tfidf"):
            self.vectorizers = _tfidf_union(self.config)
        for v in self.vectorizers:
            v.fit(texts)
        return self._combine(texts)

    def transform(self, texts):
        return self._combine([self.prepare(t) for t in texts])

    def _lexical(self, texts):
        parts = [v.transform(texts) for v in self.vectorizers]
        return sp.hstack(parts, format="csr") / np.sqrt(len(parts))

    def _embed(self, texts):
        if self.embedding_cache is not None and all(t in self.embedding_cache for t in texts):
            return np.stack([self.embedding_cache[t] for t in texts])
        if self.encoder is None:
            from sentence_transformers import SentenceTransformer
            self.encoder = SentenceTransformer(str(self.encoder_path), device="cpu", local_files_only=True)
            self.encoder.max_seq_length = self.config["max_length"]
        return self.encoder.encode(["query: " + t for t in texts],
            batch_size=self.config["embedding_batch_size"], normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False).astype(np.float32)

    def _combine(self, texts):
        if self.variant.startswith("tfidf"):
            return self._lexical(texts)
        z = self._embed(texts)
        if self.variant == "e5":
            return z
        # Equal-weight early fusion; each block has unit norm before scaling.
        return sp.hstack([sp.csr_matrix(z) * np.sqrt(.5), self._lexical(texts) * np.sqrt(.5)], format="csr")


def duplicate_weights(rows, source_balance=False):
    """Prefix copies of one scenario/language share one unit of weight, then classes balance.

    With source_balance, every (synthetic?, label) cell gets equal total weight.
    Pass 1 showed why: synthetic multilingual rows were ~7% of the loss, so only a
    nearly unregularised model (C at the grid edge) fitted them.
    """
    counts = {}
    for r in rows:
        counts[(r["scenario_group_id"], r["language"])] = counts.get((r["scenario_group_id"], r["language"]), 0) + 1
    w = np.array([1.0 / counts[(r["scenario_group_id"], r["language"])] for r in rows])
    cells = [(bool(r["synthetic"]) if source_balance else None, r["label"]) for r in rows]
    total = w.sum()
    present = set(cells)
    sums = {c: w[[k == c for k in cells]].sum() for c in present}
    return w * np.array([total / (len(present) * sums[c]) for c in cells])


class CalibratedHead:
    """Logistic regression plus Platt scaling fitted on grouped out-of-fold scores."""

    def __init__(self, c, seed=42, source_balance=False):
        self.lr = LogisticRegression(C=c, max_iter=5000, random_state=seed)
        self.source_balance = source_balance
        self.platt = None

    def fit(self, x, rows):
        y = np.array([r["label"] == "scam" for r in rows], dtype=int)
        self.lr.fit(x, y, sample_weight=duplicate_weights(rows, self.source_balance))
        return self

    def raw(self, x):
        return self.lr.predict_proba(x)[:, 1]

    def set_calibration(self, oof_raw, rows):
        y = np.array([r["label"] == "scam" for r in rows], dtype=int)
        logit = _logit(oof_raw).reshape(-1, 1)
        self.platt = LogisticRegression(C=1e4, max_iter=1000).fit(
            logit, y, sample_weight=duplicate_weights(rows, self.source_balance))

    def calibrate(self, raw):
        if self.platt is None:
            return np.asarray(raw)
        return self.platt.predict_proba(_logit(raw).reshape(-1, 1))[:, 1]

    def predict_proba(self, x):
        p = self.calibrate(self.raw(x))
        return np.c_[1 - p, p]


def _logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))
