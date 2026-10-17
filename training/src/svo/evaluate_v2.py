"""Once-only held-out comparison of every frozen v2 candidate and the shipped v1 bundle.

All models see identical rows. `test_id_v1_rows` is the 115-row v1 test set, which
was already exposed by the v1 report: it is comparable with RESULTS.md but is not
untouched evidence. `test_id_new_rows` (UCI ham groups) were never evaluated before.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from .data import digest, load_data, write_json
from .evaluate import replay, report
from .model import Runtime
from .train_v2 import group_bootstrap, stratified


def load_baseline(bundle):
    """v1 bundle checked out with core.autocrlf has CRLF text files. Verify the
    LF-normalised bytes against the manifest (same content), then load."""
    import hashlib
    bundle = Path(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text())
    for name, checksum in manifest["files"].items():
        data = (bundle / name).read_bytes()
        if checksum not in (hashlib.sha256(data).hexdigest(),
                            hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()):
            raise ValueError(f"Baseline artifact changed: {name}")
    return Runtime(bundle, verify=False)


def evaluate(runtime, rows, out, name):
    test = [r for r in rows if r["split"] == "test_id"]
    v1_rows = [r for r in test if not r["id"].startswith("uci-")]
    new_rows = [r for r in test if r["id"].startswith("uci-")]
    predictions, _ = runtime.predict_vectors([r["text"] for r in test])
    scores = [p["scam_score"] for p in predictions]
    high = runtime.config["high_risk_threshold"]
    result = {"version": runtime.version, "candidate": runtime.manifest["candidate"],
        "test_id": {**report(runtime, test), "macro_f1_ci95_group_bootstrap": group_bootstrap(test, scores, .5),
                    "source_stratified_macro_f1_at_0_5": stratified(test, scores)},
        "test_id_v1_rows": report(runtime, v1_rows),
        "test_id_new_rows_legitimate_only": {"n": len(new_rows), "high_risk_false_positive_rate":
            float(np.mean([s >= high for s, r in zip(scores, test) if r["id"].startswith("uci-")]))},
        "language_slices": {l: report(runtime, [r for r in test if r["language"] == l])
                            for l in sorted({r["language"] for r in test})},
        "source_slices": {s: report(runtime, [r for r in test if r["source_id"] == s])
                          for s in sorted({r["source_id"] for r in test})}}
    shift_rows = [r for r in rows if r["split"] == "shift_demo"]
    result["shift_demo"] = report(runtime, shift_rows)
    result["drift"] = replay(runtime, shift_rows, out / f"{name}_replay.sqlite")
    result["benign_replay"] = replay(runtime, [r for r in shift_rows if r["label"] == "legitimate"],
                                     out / f"{name}_benign_replay.sqlite")
    result["post_update_test_before_update"] = report(runtime, [r for r in rows if r["split"] == "post_update_test"])
    latencies = []
    for r in test[:50]:
        begin = time.perf_counter()
        runtime.predict(r["text"])
        latencies.append(1000 * (time.perf_counter() - begin))
    result["runtime"] = {"warm_p50_ms": float(np.percentile(latencies, 50)),
        "warm_p95_ms": float(np.percentile(latencies, 95)),
        "bundle_bytes": sum(p.stat().st_size for p in runtime.bundle.rglob("*") if p.is_file())}
    return result


def row(name, r):
    t, o, d = r["test_id"]["classifier_at_0_5"], r["test_id"]["operating_point"], r["drift"]
    v1 = r["test_id_v1_rows"]["classifier_at_0_5"]
    ci = r["test_id"].get("macro_f1_ci95_group_bootstrap") or [float("nan")] * 2
    pct = lambda x: "—" if x is None else f"{100 * x:.1f}%"
    return (f"| {name} | {t['macro_f1']:.3f} [{ci[0]:.2f}–{ci[1]:.2f}] | {v1['macro_f1']:.3f} | "
            f"{r['test_id']['source_stratified_macro_f1_at_0_5']['synthetic']:.3f} | {t['pr_auc_average_precision']:.3f} | "
            f"{pct(o['scam_precision'])} / {pct(o['scam_recall'])} | {pct(o['high_risk_false_positive_rate'])} | "
            f"{r['test_id']['review_per_100']:.0f} | {pct(d['normal_false_alert_rate'])} | "
            f"{d['reports_after_onset_to_alert'] if d['shift_detected'] else 'missed'} | "
            f"{pct(d['shifted_window_detection_rate'])} | {r['runtime']['warm_p95_ms']:.1f} |")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--baseline", default="training/runs/final/bundle")
    p.add_argument("--simulation", action="store_true")
    args = p.parse_args()
    out = Path(args.run)
    freeze = json.loads((out / "freeze.json").read_text())
    if freeze["data_sha256"] != digest(args.data):
        raise ValueError("Data changed after freeze")
    for v, info in freeze["candidates"].items():
        if digest(out / "candidates" / v / "bundle" / "manifest.json") != info["manifest_sha256"]:
            raise ValueError(f"Candidate {v} changed after freeze")
    if (out / "FINAL_EVALUATION_STARTED.json").exists():
        raise RuntimeError("Final evaluation already started. Keep its evidence; do not silently rerun on exposed sets.")
    rows = load_data(args.data, simulation=args.simulation)
    # Load and verify every bundle before the once-only marker is written.
    runtimes = {"v1_shipped": load_baseline(args.baseline),
                **{v: Runtime(out / "candidates" / v / "bundle") for v in freeze["candidates"]}}
    write_json(out / "FINAL_EVALUATION_STARTED.json", {"selected": freeze["selected"], "started_unix": time.time()})
    results = {name: evaluate(runtime, rows, out, name) for name, runtime in runtimes.items()}
    write_json(out / "comparison.json", {"selected": freeze["selected"], "results": results,
        "disclosure": "test_id_v1_rows were exposed by the v1 report; new UCI test groups are untouched. "
                      "v1_shipped was trained on the v1 split without UCI data."})
    header = ("| Model | Test macro-F1 [95% group CI] | Macro-F1 on v1 115 rows | Synthetic-only macro-F1 | PR-AUC | "
              "Operating precision / recall | Legit high-risk FPR | Review /100 | Normal false-alert windows | "
              "Alert delay (reports) | Shifted windows alerting | p95 ms |\n" + "|---" * 12 + "|")
    table = "\n".join([header] + [row(("**" + k + " (selected)**") if k == freeze["selected"] else k, r)
                                  for k, r in results.items()])
    (out / "comparison.md").write_text(table + "\n", encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
