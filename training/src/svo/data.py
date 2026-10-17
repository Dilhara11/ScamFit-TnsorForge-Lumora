"""Strict data admission and group leakage checks. No metadata is a feature."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from .preprocessing import normalize, text_hash

SPLITS = {"train", "val_select", "val_cal", "test_id", "shift_dev",
          "shift_demo", "update_train", "update_val", "post_update_test"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def load_data(path, simulation=False):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    ids, groups, texts = set(), {}, {}
    required = {"id", "text", "label", "language", "family", "scenario_group_id",
                "source_id", "source_type", "license_or_generation_method",
                "human_review_status", "synthetic", "split"}
    for row in rows:
        missing = required - row.keys()
        if missing:
            raise ValueError(f"Missing fields: {sorted(missing)}")
        if row["id"] in ids:
            raise ValueError("duplicate record id")
        ids.add(row["id"])
        if row["split"] not in SPLITS or row["label"] not in ("scam", "legitimate"):
            raise ValueError("invalid split or label")
        if not simulation and row["human_review_status"] != "approved":
            raise ValueError("Unreviewed data require explicit --simulation")
        row["text"] = normalize(row["text"])
        group = row["scenario_group_id"]
        if not isinstance(group, str) or not group:
            raise ValueError("scenario_group_id must be nonempty")
        if group in groups and groups[group] != row["split"]:
            raise ValueError(f"Group leakage: {group}")
        groups[group] = row["split"]
        h = text_hash(row["text"])
        if h in texts:
            raise ValueError("exact duplicate text; deduplicate/consolidate groups first")
        texts[h] = (row["label"], row["split"])
    counts = Counter(r["split"] for r in rows)
    if set(counts) != SPLITS:
        raise ValueError(f"Missing splits: {SPLITS - set(counts)}")
    for split in ("train", "val_select", "val_cal", "test_id", "post_update_test"):
        if {r["label"] for r in rows if r["split"] == split} != {"scam", "legitimate"}:
            raise ValueError(f"Both classes required in {split}")
    train_families = {r["family"] for r in rows if r["split"] == "train"}
    unseen = [r for r in rows if r.get("shift_type") == "unseen_mechanism"]
    if any(r["family"] in train_families for r in unseen):
        raise ValueError("Held-out mechanism present in training")
    return rows


def split_manifest(rows):
    counts = defaultdict(Counter)
    for row in rows:
        counts[row["split"]][row["label"]] += 1
    return {
        "counts": dict(counts),
        "groups": {s: len({r["scenario_group_id"] for r in rows if r["split"] == s}) for s in SPLITS},
        "review_status": dict(Counter(r["human_review_status"] for r in rows)),
        "languages": dict(Counter(r["language"] for r in rows)),
        "records": [{"id": r["id"], "group": r["scenario_group_id"], "split": r["split"],
                     "text_sha256": text_hash(r["text"])} for r in rows],
        "near_duplicate_review": "manual semantic review pending; group IDs prevent template variants crossing splits"
    }
