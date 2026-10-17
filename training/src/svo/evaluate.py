"""Once-only held-out report for an already frozen run."""
import argparse
import json
import platform
import resource
import time
import zipfile
from pathlib import Path

import numpy as np

from .data import digest, load_data, write_json
from .model import Runtime, metrics
from .monitor import Monitor


def report(runtime, rows):
    predictions, _ = runtime.predict_vectors([r["text"] for r in rows])
    scores = [p["scam_score"] for p in predictions]
    result = {"classifier_at_0_5": metrics(rows, scores),
              "operating_point": metrics(rows, scores, runtime.config["high_risk_threshold"]),
              "review_per_100": 100 * float(np.mean([p["needs_review"] for p in predictions])),
              "unknown_fraction": float(np.mean([p["is_unknown"] for p in predictions]))}
    for label, predicate in (("unseen_mechanism", lambda r: r.get("shift_type") == "unseen_mechanism" and r["label"] == "scam"),
                             ("benign_novelty", lambda r: r.get("shift_type") == "benign_novelty")):
        indices = [i for i, r in enumerate(rows) if predicate(r)]
        result[label] = {"n": len(indices), "review_routing_rate":
            float(np.mean([predictions[i]["needs_review"] for i in indices])) if indices else None,
            "high_risk_rate": float(np.mean([predictions[i]["decision"] == "high_risk" for i in indices])) if indices else None,
            "classifier_positive_rate_at_0_5": float(np.mean([scores[i] >= .5 for i in indices])) if indices else None}
    return result


def replay(runtime, rows, db_path):
    ordered = sorted(rows, key=lambda r: r["event_index"])
    if len({r["event_index"] for r in ordered}) != len(ordered):
        raise ValueError("Replay requires unique explicit event_index values")
    monitor = Monitor(runtime, db_path)
    start = time.perf_counter()
    first_shift = next((i+1 for i,r in enumerate(ordered) if r.get("shift_type") not in (None, "none", "normal")), None)
    outputs, first_candidate = [], None
    for i, row in enumerate(ordered, 1):
        outputs.append(monitor.process(row["text"], row["id"]))
        if first_candidate is None and any(c["candidate_variant"] for c in monitor.queue()):
            first_candidate = i
    windows = monitor.db.execute("SELECT seq,alert FROM windows ORDER BY seq").fetchall()
    normal = [bool(a) for seq,a in windows if first_shift is None or seq < first_shift]
    shifted = [bool(a) for seq,a in windows if first_shift is not None and seq >= first_shift + runtime.config["window_size"] - 1]
    first_alert = next((seq for seq,a in windows if a and first_shift is not None and seq >= first_shift), None)
    clusters = monitor.queue()
    candidates = [c for c in clusters if c["candidate_variant"]]
    cluster_labels = {}
    for row, out in zip(ordered, outputs):
        cid = out["cluster_id_or_null"]
        if cid is not None:
            cluster_labels.setdefault(cid, []).append(row)
    candidate_scam = [any(r["label"] == "scam" and r.get("shift_type") == "unseen_mechanism"
                          for r in cluster_labels[c["cluster_id"]]) for c in candidates]
    purity = []
    for c in candidates:
        from collections import Counter
        counts = Counter(r["family"] for r in cluster_labels[c["cluster_id"]])
        purity.append(max(counts.values()) / sum(counts.values()))
    result = {"messages": len(ordered), "shift_onset_1_based": first_shift,
        "normal_window_count": len(normal), "normal_false_alert_rate": float(np.mean(normal)) if normal else None,
        "fully_shifted_window_count": len(shifted), "shifted_window_detection_rate": float(np.mean(shifted)) if shifted else None,
        "first_drift_alert_1_based": first_alert,
        "reports_after_onset_to_alert": first_alert-first_shift+1 if first_alert and first_shift else None,
        "shifted_reports_to_alert": sum(r.get("shift_type") not in (None,"normal","none") for r in ordered[first_shift-1:first_alert]) if first_alert and first_shift else None,
        "shift_detected": first_alert is not None,
        "first_candidate_alert_1_based": first_candidate, "candidate_clusters": len(candidates),
        "candidate_alert_precision_scenario_proxy": float(np.mean(candidate_scam)) if candidate_scam else None,
        "mean_candidate_family_purity": float(np.mean(purity)) if purity else None,
        "review_per_100": 100*float(np.mean([p["needs_review"] for p in outputs])),
        "unresolved_clusters": sum(c["status"] == "pending" for c in clusters),
        "replay_seconds": time.perf_counter()-start,
        "response": "persisted review queue and drift alerts; no automatic retraining",
        "unique_text_is_not_independent_source": True}
    monitor.close()
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--simulation", action="store_true")
    args = p.parse_args()
    out = Path(args.run)
    freeze = json.loads((out / "freeze.json").read_text())
    if freeze["data_sha256"] != digest(args.data) or freeze["manifest_sha256"] != digest(out / "bundle/manifest.json"):
        raise ValueError("Data or bundle changed after freeze")
    if (out / "FINAL_EVALUATION_STARTED.json").exists():
        raise RuntimeError("Final evaluation already started. Keep its evidence; do not silently rerun on exposed sets.")
    rows = load_data(args.data, simulation=args.simulation)
    write_json(out / "FINAL_EVALUATION_STARTED.json", {"version": freeze["version"], "started_unix": time.time()})
    begin = time.perf_counter()
    runtime = Runtime(out / "bundle")
    # Include encoder cold load in the measured startup.
    runtime.predict("A routine service information notice.")
    cold = time.perf_counter()-begin
    test = [r for r in rows if r["split"] == "test_id"]
    test_report = report(runtime, test)
    source_slices = {source: report(runtime, [r for r in test if r["source_id"] == source])
                     for source in sorted({r["source_id"] for r in test})}
    slices = {}
    for language in sorted({r["language"] for r in test}):
        subset = [r for r in test if r["language"] == language]
        slices[language] = {**report(runtime, subset),
            "reviewed": all(r["human_review_status"] == "approved" for r in subset),
            "small_sample": len(subset) < 100}
    latencies = []
    for r in test[:50]:
        begin = time.perf_counter()
        runtime.predict(r["text"])
        latencies.append(1000 * (time.perf_counter()-begin))
    shift_rows = [r for r in rows if r["split"] == "shift_demo"]
    drift = replay(runtime, shift_rows, out / "final_replay.sqlite")
    post = report(runtime, [r for r in rows if r["split"] == "post_update_test"])
    # Explicit benign-only stream tests unfamiliar legitimate messages separately.
    benign = [r for r in shift_rows if r["label"] == "legitimate"]
    benign_replay = replay(runtime, benign, out / "benign_replay.sqlite") if benign else None
    development = json.loads((out / "development.json").read_text())
    scorecard = {"version": runtime.version, "scope": runtime.config["scope"],
        "data_sha256": digest(args.data), "split_manifest_sha256": digest(out / "split_manifest.json"),
        "candidate": runtime.manifest["candidate"], "test_id": test_report, "language_slices": slices,
        "source_slices": source_slices, "human_validated_languages": [],
        "shift_demo": report(runtime, shift_rows), "drift": drift, "benign_replay": benign_replay,
        "update": {"status": "not_run_no_approved_support_or_budget", "before": post, "after": None},
        "runtime": {"platform": platform.platform(), "processor": platform.processor(),
            "cold_start_seconds": cold, "warm_p50_ms": float(np.percentile(latencies,50)),
            "warm_p95_ms": float(np.percentile(latencies,95)), "latency_samples": len(latencies),
            "peak_process_rss_kib_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "bundle_bytes": sum(p.stat().st_size for p in (out / "bundle").rglob("*") if p.is_file())},
        "targets": {"precision": .9, "recall": .8, "warm_p95_ms": 2000, "normal_false_alert_rate": .05},
        "development": development,
        "limitations": ["No real-world prevalence or loss-prevention claims", "Uncalibrated model scores",
            "Distinct text is not proof of independent reporters", "One predetermined shifted replay",
            "Small language slices; unreviewed data do not establish language quality",
            "No controlled model update completed", "Lexical monitoring if TF-IDF selected"]}
    write_json(out / "scorecard.json", scorecard)
    exports = Path(__file__).resolve().parents[2] / "exports"
    exports.mkdir(exist_ok=True)
    archive = exports / f"runtime_bundle_{runtime.version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted((out / "bundle").rglob("*")):
            if file.is_file(): z.write(file, str(Path("bundle") / file.relative_to(out / "bundle")))
        for file in sorted(Path(__file__).parent.glob("*.py")):
            z.write(file, str(Path("src/svo") / file.name))
        root = Path(__file__).resolve().parents[2]
        for name in ("requirements-runtime.txt", "requirements-training.txt", "BUNDLE_README.md", "LICENSE"):
            if (root / name).exists(): z.write(root / name, name)
    write_json(exports / f"{runtime.version}.sha256.json", {archive.name: digest(archive)})
    write_json(out / "FINAL_EVALUATION_COMPLETE.json", {"version": runtime.version,
        "scorecard_sha256": digest(out / "scorecard.json"), "archive_sha256": digest(archive)})
    print(json.dumps({"scorecard": str(out / "scorecard.json"), "archive": str(archive),
                      "test_macro_f1": test_report["classifier_at_0_5"]["macro_f1"], "drift_detected": drift["shift_detected"]}))


if __name__ == "__main__":
    main()
