"""Development-only fitting; final evaluation is a separate, guarded command."""
import argparse
import importlib.metadata
import json
import platform
import shutil
import time
from pathlib import Path

import joblib
import numpy as np

from .artifacts import seal_bundle
from .data import digest, load_data, split_manifest, write_json
from .model import Features, Runtime, fit_head, metrics, select_threshold


def dense(x):
    return x.toarray() if hasattr(x, "toarray") else np.asarray(x)


def tune_monitor(features, reference, calibration, shift_dev, config):
    x = features.transform([r["text"] for r in calibration])
    novelty = 1 - np.clip(dense(x @ reference.T), -1, 1).max(axis=1)
    threshold = float(np.quantile(novelty, 0.95))
    # Repeated normal replays resample whole groups; no final labels/traffic used.
    groups = sorted({r["scenario_group_id"] for r in calibration})
    fractions = []
    rng = np.random.default_rng(config["seed"])
    for _ in range(20):
        sampled = rng.choice(groups, size=max(30, len(groups)), replace=True)
        order = [i for g in sampled for i, r in enumerate(calibration) if r["scenario_group_id"] == g]
        flags = novelty[order] > threshold
        for end in range(config["window_size"], len(flags)+1, config["window_stride"]):
            fractions.append(float(flags[end-config["window_size"]:end].mean()))
    drift_threshold = float(np.quantile(fractions, .95)) if fractions else 1.0
    # Threshold selected from positive/negative same-scenario development pairs.
    z = features.transform([r["text"] for r in shift_dev])
    similarities = dense(z @ z.T)
    pairs = [(float(similarities[i,j]), shift_dev[i]["scenario_group_id"] == shift_dev[j]["scenario_group_id"])
             for i in range(len(shift_dev)) for j in range(i)]
    thresholds = np.linspace(.3, .95, 14)
    if pairs and any(label for _, label in pairs):
        from sklearn.metrics import f1_score
        cluster = max(thresholds, key=lambda t: f1_score(
            [p[1] for p in pairs], [p[0] >= t for p in pairs], zero_division=0))
        cluster_status = "selected_on_shift_dev_pair_f1"
    else:
        cluster, cluster_status = .8, "provisional_no_related_development_pairs"
    return {"novelty_threshold": threshold, "drift_unknown_threshold": drift_threshold,
            "cluster_similarity": float(cluster), "cluster_threshold_status": cluster_status,
            "normal_calibration_windows": len(fractions),
            "normal_calibration_elevated_fraction": float(np.mean(np.array(fractions) > drift_threshold)) if fractions else None}


def train(args):
    started = time.monotonic()
    root = Path(__file__).resolve().parents[2]
    config = json.loads(Path(args.config).read_text())
    rows = load_data(args.data, simulation=args.simulation)
    partitions = {s: [r for r in rows if r["split"] == s] for s in ("train", "val_select", "val_cal", "shift_dev")}
    out = Path(args.run)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "split_manifest.json", split_manifest(rows))
    write_json(out / "config.json", config)
    ledger, winners = [], []
    kinds = ["tfidf"] + (["e5"] if args.encoder else [])
    for kind in kinds:
        features = Features(kind, config, args.encoder)
        begin = time.monotonic()
        x = features.fit([r["text"] for r in partitions["train"]])
        val_x = features.transform([r["text"] for r in partitions["val_select"]])
        best = None
        for c in config["c_values"]:
            head = fit_head(x, partitions["train"], c)
            scores = head.predict_proba(val_x)[:, 1]
            m = metrics(partitions["val_select"], scores)
            ledger.append({"candidate": kind, "C": c, "val_select": m})
            if best is None or m["macro_f1"] > best[0]:
                best = (m["macro_f1"], features, head, x, kind, c)
        winners.append(best)
        ledger[-1]["feature_and_training_seconds"] = time.monotonic() - begin
    winner = winners[0]
    if len(winners) > 1 and winners[1][0] >= winner[0] - .02:
        winner = winners[1]
    _, features, head, reference, kind, c = winner
    cal = partitions["val_cal"]
    scores = head.predict_proba(features.transform([r["text"] for r in cal]))[:, 1]
    high, target_met = select_threshold(cal, scores, config)
    monitor_config = tune_monitor(features, reference, cal, partitions["shift_dev"], config)
    scope = "unreviewed_mixed_source_demonstration" if args.simulation else "reviewed_dataset_evaluation"
    decision = {**config, **monitor_config, "high_risk_threshold": high,
                "low_risk_threshold": min(config["low_risk_threshold"], high),
                "operating_target_met": target_met, "scope": scope,
                "scores_calibrated": False, "monitor_representation": kind,
                "window_mode": "short_20_report_demo" if config["window_size"] == 20 else "configured"}
    bundle = out / "bundle"
    bundle.mkdir()
    if kind == "e5":
        shutil.copytree(args.encoder, bundle / "encoder")
    features.encoder = None
    features.encoder_path = None
    joblib.dump({"features": features, "head": head, "reference": reference,
                 "metadata": [{"id": r["id"], "family": r["family"], "label": r["label"]} for r in partitions["train"]]},
                bundle / "model.joblib", compress=3)
    write_json(bundle / "decision_config.json", decision)
    (bundle / "model_card.md").write_text(
        f"# Scam Variant Observatory\n\nScope: {scope}. Candidate: {kind}; C={c}.\n"
        "Scores are not calibrated real-world probabilities. Low risk does not mean safe. "
        "Novelty is a review signal, not proof of fraud or concept drift. "
        "Supported language quality is limited to reported evaluation slices. "
        "TF-IDF monitoring is lexical, not semantic. The short window is demo mode. "
        "No online learning; analyst confirmation does not retrain automatically. "
        "Joblib artifacts must only be loaded from trusted team-controlled bundles.\n")
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    source_hashes = {str(p.relative_to(root)): digest(p) for p in sorted((root / "src").rglob("*.py"))}
    encoder_revision = None
    if args.encoder and (Path(args.encoder) / "revision.json").exists():
        encoder_revision = json.loads((Path(args.encoder) / "revision.json").read_text())
    manifest = seal_bundle(bundle, {"candidate": kind, "C": c, "data_sha256": digest(args.data),
        "split_sha256": digest(out / "split_manifest.json"), "seed": config["seed"],
        "packages": packages, "python": platform.python_version(), "source_hashes": source_hashes,
        "encoder_revision": encoder_revision if kind == "e5" else None,
        "preprocessing": "NFC and whitespace normalization", "scope": scope})
    runtime = Runtime(bundle)
    fixture = [r["text"] for r in partitions["val_select"][:8]]
    if kind == "e5":
        features.encoder_path = bundle / "encoder"
    before = head.predict_proba(features.transform(fixture))[:, 1]
    after = np.array([p["scam_score"] for p in runtime.predict_vectors(fixture)[0]])
    if not np.allclose(before, after, atol=1e-6):
        raise RuntimeError("Export inference parity failed")
    write_json(out / "development.json", {"experiments": ledger, "selected": kind,
        "selection_reason": "E5 within 0.02 macro-F1 when available; otherwise best TF-IDF on val_select",
        "candidate_b": "completed" if args.encoder else "skipped_setup_or_download_budget",
        "candidate_c": "skipped_one_hour_budget", "operating_target_met": target_met,
        "calibration": metrics(cal, scores, high), "monitoring": monitor_config,
        "runtime_parity_max_score_difference": float(np.max(np.abs(before-after))),
        "train_seconds": time.monotonic()-started,
        "update": "deferred_requires_separately_approved_support_groups_and_budget"})
    write_json(out / "freeze.json", {"version": manifest["version"], "data_sha256": digest(args.data),
        "manifest_sha256": digest(bundle / "manifest.json"), "final_evaluation": "not_run"})
    print(json.dumps({"run": str(out), "bundle": str(bundle), "version": manifest["version"],
                      "candidate": kind, "target_met": target_met}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--config", default="training/configs/experiment.json")
    parser.add_argument("--run", required=True)
    parser.add_argument("--encoder", help="Local downloaded encoder; no hub access during training")
    parser.add_argument("--simulation", action="store_true")
    train(parser.parse_args())


if __name__ == "__main__":
    main()
