"""V2 development-only training: grouped repeated CV, calibration, comparable candidates.

Changes from svo.train, each answering a measured v1 failure:
- shared masking for all sources (v1: mask tokens identified the scam-only CSV);
- train+val_select+val_cal pooled for grouped CV (v1: 2 legitimate scenarios each
  in val_select/val_cal, so C and thresholds were fitted to a handful of groups);
- final model refitted on the pooled development groups;
- Platt scaling and thresholds from out-of-fold scores (v1: uncalibrated scores,
  fixed 0.2 low-risk cut, 100% review workload);
- out-of-group novelty, source-balanced drift simulation with row-level arrival
  order and the real two-window alert rule (v1: thresholds fitted in-sample);
- cluster similarity bounded below by unrelated-pair similarity (v1: 0.3 grid edge).
test_id, shift_demo and post_update_test are never read here.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from .artifacts import seal_bundle
from .data import digest, load_data, split_manifest, write_json
from .model import Runtime, metrics
from .v2 import CalibratedHead, Features2, canonical

DEV = ("train", "val_select", "val_cal")


def dense(x):
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)


def labels(rows):
    return np.array([r["label"] == "scam" for r in rows], dtype=int)


def folds(rows, k, seed):
    groups = [r["scenario_group_id"] for r in rows]
    return list(StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed).split(rows, labels(rows), groups))


def group_bootstrap(rows, scores, threshold, n=500, seed=0):
    """95% interval for macro-F1, resampling scenario groups (translations are not independent)."""
    from sklearn.metrics import f1_score
    rng = np.random.default_rng(seed)
    by_group = {}
    for i, r in enumerate(rows):
        by_group.setdefault(r["scenario_group_id"], []).append(i)
    keys = list(by_group)
    y, pred, out = labels(rows), np.asarray(scores) >= threshold, []
    for _ in range(n):
        idx = np.concatenate([by_group[keys[j]] for j in rng.integers(0, len(keys), len(keys))])
        out.append(f1_score(y[idx], pred[idx], average="macro", labels=[0, 1], zero_division=0))
    return [float(np.quantile(out, .025)), float(np.quantile(out, .975))]


def stratified(rows, scores, threshold=.5):
    """Macro-F1 inside each source stratum; both strata contain both classes.

    Pooled macro-F1 is dominated by real-scam vs real-chat style; the mean of the
    per-stratum scores cannot be won by recognising the source alone.
    """
    out = {}
    for name, pred in (("synthetic", lambda r: r["synthetic"]), ("real", lambda r: not r["synthetic"])):
        idx = [i for i, r in enumerate(rows) if pred(r)]
        out[name] = metrics([rows[i] for i in idx], np.asarray(scores)[idx], threshold)["macro_f1"]
    out["mean"] = float(np.mean(list(out.values())))
    langs = sorted({r["language"] for r in rows})
    out["synthetic_by_language"] = {l: metrics(*zip(*[(r, s) for r, s in zip(rows, scores)
        if r["synthetic"] and r["language"] == l]), threshold)["macro_f1"] for l in langs
        if any(r["synthetic"] and r["language"] == l for r in rows)}
    return out


def cross_validate(variant, dev, config, cache):
    """Mean out-of-fold raw scores per C over repeated grouped folds; vectorizers fit per fold."""
    sums = {c: np.zeros(len(dev)) for c in config["c_values"]}
    fold_f1 = {c: [] for c in config["c_values"]}
    for repeat in range(config["cv_repeats"]):
        for tr, va in folds(dev, config["cv_folds"], config["seed"] + repeat):
            features = Features2(variant, config)
            features.embedding_cache = cache
            xtr = features.fit([dev[i]["text"] for i in tr])
            xva = features.transform([dev[i]["text"] for i in va])
            for c in config["c_values"]:
                s = CalibratedHead(c, config["seed"], config.get("source_balance", False)).fit(xtr, [dev[i] for i in tr]).raw(xva)
                sums[c][va] += s
                fold_f1[c].append(metrics([dev[i] for i in va], s)["macro_f1"])
    return {c: (sums[c] / config["cv_repeats"], fold_f1[c]) for c in config["c_values"]}


def high_threshold(rows, scores, config):
    best = None
    for t in np.unique(scores):
        m = metrics(rows, scores, float(t))
        if m["scam_precision"] >= config["precision_target"]:
            key = (m["scam_recall"], float(t))
            best = key if best is None or key > best else best
    if best is None:
        return 1.01, False, None
    return best[1], best[0] >= config["recall_target"], best[0]


def low_threshold(rows, scores, config, high):
    """Largest cut that sends at most low_risk_max_scam_leak of dev scams to low risk."""
    scam = np.sort(np.asarray(scores)[labels(rows) == 1])
    k = int(np.floor(config["low_risk_max_scam_leak"] * len(scam)))
    return float(min(scam[k] if k < len(scam) else 1.0, high))


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    cum = np.cumsum(weights[order]) / weights.sum()
    return float(values[order][np.searchsorted(cum, q)])


def source_weights(rows):
    sources = [r["source_type"] for r in rows]
    counts = {s: sources.count(s) for s in set(sources)}
    return np.array([1.0 / counts[s] for s in sources])


def tune_monitor(features, x_dev, dev, shift_dev, config):
    sim = np.clip(dense(x_dev @ x_dev.T), -1, 1)
    groups = np.array([r["scenario_group_id"] for r in dev])
    same = groups[:, None] == groups[None, :]
    novelty = 1 - np.where(same, -1, sim).max(axis=1)  # nearest *other* scenario
    weights = source_weights(dev)
    threshold = weighted_quantile(novelty, weights, config["novelty_quantile"])
    flags = novelty > threshold
    # Normal streams: rows arrive one by one (as in the replay), sources balanced.
    rng = np.random.default_rng(config["seed"])
    w, step = config["window_size"], config["window_stride"]
    streams = [flags[rng.choice(len(dev), config["drift_stream_length"], p=weights / weights.sum())]
               for _ in range(config["drift_simulations"])]
    chosen, rate = 1.0, 0.0
    for d in np.arange(0, w + 1) / w:
        alerts = []
        for s in streams:
            elevated = [s[e - w:e].mean() > d for e in range(w, len(s) + 1, step)]
            alerts += [all(elevated[i - config["consecutive_windows"] + 1:i + 1])
                       for i in range(config["consecutive_windows"] - 1, len(elevated))]
        rate = float(np.mean(alerts))
        if rate <= config["normal_alert_target"]:
            chosen = float(d)
            break
    # Cluster cut: best same-scenario pair F1 on shift_dev, never below the 99th
    # percentile of unrelated development pairs (v1 selected the 0.3 grid edge).
    floor = float(np.quantile(sim[~same], .99))
    z = dense(features.transform([r["text"] for r in shift_dev]))
    zs = z @ z.T
    pairs = [(zs[i, j], shift_dev[i]["scenario_group_id"] == shift_dev[j]["scenario_group_id"])
             for i in range(len(shift_dev)) for j in range(i)]
    from sklearn.metrics import f1_score
    grid = [t for t in np.round(np.arange(.30, .96, .01), 2) if t >= floor] or [round(floor, 2)]
    cluster = max(grid, key=lambda t: (f1_score([p[1] for p in pairs], [p[0] >= t for p in pairs], zero_division=0), -t))
    return {"novelty_threshold": threshold, "novelty_method": "out-of-group nearest neighbour, source-balanced 95th percentile",
            "drift_unknown_threshold": chosen, "simulated_normal_alert_rate": rate,
            "cluster_similarity": float(cluster), "cluster_similarity_floor_unrelated_p99": floor,
            "cluster_threshold_status": "shift_dev_pair_f1_above_unrelated_floor"}


def embed_all(rows, encoder, config, cache_dir):
    """Frozen E5 embeddings for every canonical text, cached by data/encoder/settings."""
    from .v2 import Features2 as F
    texts = sorted({canonical(r["text"]) for r in rows})
    revision = json.loads((Path(encoder) / "revision.json").read_text())["revision"]
    key = hashlib.sha256(json.dumps([texts, revision, config["max_length"], "query: ", "mean", "v2-canonical"]).encode()).hexdigest()[:16]
    path = Path(cache_dir) / f"e5_{key}.npy"
    if path.exists():
        z = np.load(path)
    else:
        f = F("e5", config, encoder)
        z = f._embed(texts)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, z)
    return dict(zip(texts, z)), {"path": str(path), "revision": revision, "texts": len(texts)}


def export(out, variant, c, config, dev, cache, encoder, oof_raw, shift_dev, scope, data_path, root):
    features = Features2(variant, config, encoder)
    features.embedding_cache = cache
    x_dev = features.fit([r["text"] for r in dev])
    head = CalibratedHead(c, config["seed"], config.get("source_balance", False)).fit(x_dev, dev)
    head.set_calibration(oof_raw, dev)
    oof = head.calibrate(oof_raw)
    high, target_met, dev_recall = high_threshold(dev, oof, config)
    low = low_threshold(dev, oof, config, high)
    monitor = tune_monitor(features, x_dev, dev, shift_dev, config)
    bundle = out / "bundle"
    bundle.mkdir(parents=True)
    if features.kind == "e5":
        # .cache holds hub download metadata; hashing it would make the bundle
        # irreproducible from a fresh download of the same pinned revision.
        shutil.copytree(encoder, bundle / "encoder", ignore=shutil.ignore_patterns("onnx", ".cache"))
    features.encoder = features.encoder_path = features.embedding_cache = None
    decision = {**config, **monitor, "high_risk_threshold": float(high), "low_risk_threshold": low,
                "operating_target_met": bool(target_met), "scope": scope, "scores_calibrated": True,
                "calibration": "Platt scaling on grouped out-of-fold scores, class-balanced prior",
                "monitor_representation": variant, "window_mode": "short_20_report_demo"}
    joblib.dump({"features": features, "head": head, "reference": x_dev,
                 "metadata": [{"id": r["id"], "family": r["family"], "label": r["label"]} for r in dev]},
                bundle / "model.joblib", compress=3)
    write_json(bundle / "decision_config.json", decision)
    (bundle / "model_card.md").write_text(
        f"# Scam Variant Observatory v2\n\nScope: {scope}. Candidate: {variant}; C={c}.\n"
        "Scores are Platt-calibrated on grouped out-of-fold development scores under a balanced "
        "class prior; they are not real-world fraud probabilities at deployment prevalence. "
        "All text passes the same masking (svo.v2.canonical) at training and inference. "
        "Low risk does not mean safe. Novelty is a review signal, not proof of fraud or drift. "
        "Joblib artifacts must only be loaded from trusted team-controlled bundles.\n", encoding="utf-8")
    source_hashes = {str(p.relative_to(root)).replace("\\", "/"): digest(p) for p in sorted((root / "src").rglob("*.py"))}
    revision = json.loads((Path(encoder) / "revision.json").read_text()) if features.kind == "e5" else None
    manifest = seal_bundle(bundle, {"candidate": variant, "C": c, "data_sha256": digest(data_path),
        "seed": config["seed"], "python": platform.python_version(), "source_hashes": source_hashes,
        "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
        "encoder_revision": revision, "preprocessing": "NFC/whitespace + svo.v2.canonical shared masking"
        if variant != "tfidf_char_raw" else "NFC/whitespace only (v1 ablation)", "scope": scope})
    fixture = [r["text"] for r in dev[:8]]
    features.encoder_path = bundle / "encoder" if features.kind == "e5" else None
    before = head.predict_proba(features.transform(fixture))[:, 1]
    features.encoder = None
    after = np.array([p["scam_score"] for p in Runtime(bundle).predict_vectors(fixture)[0]])
    if not np.allclose(before, after, atol=1e-5):
        raise RuntimeError("Export inference parity failed")
    return manifest, {"dev_oof_calibrated_at_operating_point": metrics(dev, oof, high),
        "dev_oof_recall_at_precision_target": dev_recall, "operating_target_met": bool(target_met),
        "high_risk_threshold": float(high), "low_risk_threshold": low, "monitoring": monitor,
        "parity_max_difference": float(np.max(np.abs(before - after)))}


def train(args):
    started = time.monotonic()
    root = Path(__file__).resolve().parents[2]
    config = json.loads(Path(args.config).read_text())
    rows = load_data(args.data, simulation=args.simulation)
    dev = [r for r in rows if r["split"] in DEV]
    shift_dev = [r for r in rows if r["split"] == "shift_dev"]
    out = Path(args.run)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "split_manifest.json", split_manifest(rows))
    write_json(out / "config.json", config)
    variants = [v for v in config["variants"] if args.encoder or not v.startswith("e5")]
    cache, cache_info = (embed_all(rows, args.encoder, config, root / "cache" / "embeddings")
                         if args.encoder else (None, None))
    ledger, best = [], {}
    for variant in variants:
        begin = time.monotonic()
        results = cross_validate(variant, dev, config, cache)
        for c, (oof, fold_f1) in results.items():
            m, strata = metrics(dev, oof), stratified(dev, oof)
            ledger.append({"candidate": variant, "C": c, "oof_at_0_5": m, "oof_source_stratified_macro_f1": strata,
                           "fold_macro_f1_mean": float(np.mean(fold_f1)), "fold_macro_f1_std": float(np.std(fold_f1))})
            # Prefer stratified OOF macro-F1, then PR-AUC, then the stronger regulariser.
            key = (round(strata["mean"], 4), round(m["pr_auc_average_precision"], 4), -c)
            if variant not in best or key > best[variant][0]:
                best[variant] = (key, c, oof)
        print(json.dumps({"cv_done": variant, "best_C": best[variant][1], "oof_stratified_macro_f1": best[variant][0][0],
                          "seconds": round(time.monotonic() - begin, 1)}), flush=True)
    eligible = [v for v in variants if v not in config["selection_excluded"]]
    top = max(eligible, key=lambda v: best[v][0])
    selected = top
    semantic = [v for v in eligible if v.startswith("e5")]
    if semantic:
        top_e5 = max(semantic, key=lambda v: best[v][0])
        if best[top_e5][0][0] >= best[top][0][0] - config["e5_preference_margin"]:
            selected = top_e5  # encoder doubles as the semantic novelty/cluster space
    scope = "unreviewed_mixed_source_demonstration" if args.simulation else "reviewed_dataset_evaluation"
    candidates = {}
    for variant in variants:
        _, c, oof = best[variant]
        manifest, details = export(out / "candidates" / variant, variant, c, config, dev, cache, args.encoder,
                                   oof, shift_dev, scope, args.data, root)
        candidates[variant] = {"version": manifest["version"], "C": c,
            "oof_at_0_5": metrics(dev, oof), "oof_source_stratified_macro_f1": stratified(dev, oof),
            "oof_macro_f1_ci95_group_bootstrap": group_bootstrap(dev, oof, .5),
            **details, "manifest_sha256": digest(out / "candidates" / variant / "bundle" / "manifest.json")}
        print(json.dumps({"exported": variant, "version": manifest["version"],
                          "target_met": details["operating_target_met"]}), flush=True)
    write_json(out / "development.json", {"experiments": ledger, "candidates": candidates, "selected": selected,
        "selection_rule": f"max grouped OOF source-stratified macro-F1 (tie: PR-AUC, smaller C) among {eligible}; "
                          f"prefer best E5 variant within {config['e5_preference_margin']}",
        "excluded_from_selection": config["selection_excluded"], "embedding_cache": cache_info,
        "development_pool": {"rows": len(dev), "groups": len({r['scenario_group_id'] for r in dev}),
                             "legitimate_groups_by_source": {s: len({r['scenario_group_id'] for r in dev if r['label'] == 'legitimate' and r['source_type'] == s}) for s in {r['source_type'] for r in dev}}},
        "train_seconds": time.monotonic() - started,
        "update": "deferred_requires_separately_approved_support_groups"})
    # Freeze before anything reads held-out data.
    write_json(out / "freeze.json", {"selected": selected, "data_sha256": digest(args.data),
        "candidates": {v: {"version": d["version"], "manifest_sha256": d["manifest_sha256"]} for v, d in candidates.items()},
        "final_evaluation": "not_run"})
    print(json.dumps({"run": str(out), "selected": selected, "seconds": round(time.monotonic() - started, 1)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--config", default="training/configs/experiment_v2.json")
    parser.add_argument("--run", required=True)
    parser.add_argument("--encoder", help="Local downloaded encoder; no hub access during training")
    parser.add_argument("--simulation", action="store_true")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
