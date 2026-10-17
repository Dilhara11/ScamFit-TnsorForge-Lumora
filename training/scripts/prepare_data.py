"""Build private grouped data from the supplied CSV and private multilingual seeds.

Unknown-provenance source rows are admitted only with --allow-unverified-source and
remain unreviewed. This is not an assertion of licence/privacy compliance.
"""
import argparse
import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from svo.data import digest, load_data, write_json
from svo.preprocessing import normalize, text_hash


def scrub(text, entities=""):
    text = normalize(text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?i)(?:https?://|www\.)\S+|\b(?:[a-z0-9-]+\.)+(?:com|net|org|lk|io|xyz|co|me|uk|in|info|site|top|link|live|online|click|ly)\b\S*", "[URL]", text)
    text = re.sub(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b\S*", "[URL]", text)
    text = re.sub(r"\+?\d[\d\s()./-]{3,}\d", "[NUMBER]", text)
    text = re.sub(r"\d+", "[NUMBER]", text)
    for entity in re.split(r"[,;|\[\]{}\"']", entities):
        entity = entity.strip()
        if len(entity) >= 3:
            text = re.sub(re.escape(entity), "[ENTITY]", text, flags=re.I)
    # Remove remaining title-cased tokens conservatively, including possible names.
    text = re.sub(r"\b[A-Z][a-z]{2,}\b", "[NAME_OR_WORD]", text)
    return normalize(text)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv")
    p.add_argument("--seeds", required=True)
    p.add_argument("--output", default="training/data/processed/messages.jsonl")
    p.add_argument("--allow-unverified-source", action="store_true")
    p.add_argument("--source-limit", type=int, default=400)
    args = p.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Refusing to overwrite a prepared dataset; use a new output path")
    rows, seen = [], set()
    seeds = json.loads(Path(args.seeds).read_text())
    for seed in seeds:
        for language, text in seed["texts"].items():
            for variant, prefix in enumerate(("", {"en":"Notice: ", "si":"දැනුම්දීම: ", "ta":"அறிவிப்பு: ",
                                                   "singlish":"Danweemai: ", "tanglish":"Arivippu: "}[language])):
                text_variant = normalize(prefix + text)
                rows.append({"id": f"{seed['group']}-{seed['label']}-{language}-{variant}", "text": text_variant,
                    "label": seed["label"], "language": language, "family": seed["family"],
                    "scenario_group_id": seed["group"], "parent_id": seed["group"],
                    "generation_batch_id": "codex-local-multilingual-v1",
                    "source_id": "team-synthetic-v1", "source_type": "synthetic",
                    "license_or_generation_method": "AI-assisted fictional seed writing and explicit translations; private testing only",
                    "human_review_status": "unreviewed", "synthetic": True, "split": seed["split"],
                    "shift_type": seed.get("shift_type", "normal"),
                    "impersonation_target": "fictional_service", "requested_action": seed["family"]})
                if text_hash(text_variant) in seen:
                    raise ValueError("Duplicate synthetic seed text")
                seen.add(text_hash(text_variant))
    audit = {"synthetic_seed_groups": len({s["group"] for s in seeds}),
             "synthetic_rows": len(rows), "source_status": "not_used", "rejected": {}}
    if args.csv:
        if not args.allow_unverified_source:
            raise ValueError("Source provenance missing; explicit --allow-unverified-source required for local demonstration")
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            raw = list(csv.DictReader(f))
        audit.update({"source_status": "user_supplied_unknown_licence_unverified", "source_sha256": digest(args.csv),
                      "raw_rows": len(raw), "raw_language_counts": dict(Counter(r.get("language", "") for r in raw))})
        random.Random(42).shuffle(raw)
        admitted, reasons = [], Counter()
        mapping = {"banking": "credential_theft", "delivery": "advance_fee", "government": "impersonation", "telecom": "impersonation"}
        for record in raw:
            if None in record or record.get("language") != "English" or record.get("scam_type") not in mapping:
                reasons["non_english_ambiguous_label_or_malformed"] += 1
                continue
            try:
                text = scrub(record["text"], record.get("named_entity", ""))
            except ValueError:
                reasons["invalid_text"] += 1
                continue
            if len(text) < 40 or len(text) > 800:
                reasons["length"] += 1
                continue
            fingerprint = re.sub(r"[^a-z ]", "", text.lower())
            key = hashlib.sha256(fingerprint.encode()).hexdigest()
            if key in seen or text_hash(text) in seen:
                reasons["duplicate_template"] += 1
                continue
            seen.add(key)
            seen.add(text_hash(text))
            admitted.append((key, text, mapping[record["scam_type"]]))
            if len(admitted) >= args.source_limit:
                break
        # Consolidate likely lexical paraphrases before assigning any source splits.
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.neighbors import NearestNeighbors
        if admitted:
            vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(3,5), max_features=30000)
            x = vectorizer.fit_transform([a[1] for a in admitted])
            # Grouping features are used only for leakage consolidation, never prediction.
            neighbors = NearestNeighbors(metric="cosine", radius=.25).fit(x).radius_neighbors(x, return_distance=False)
            parent = list(range(len(admitted)))
            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i
            for i, near in enumerate(neighbors):
                for j in near:
                    parent[find(int(j))] = find(i)
            for i,(key,text,family) in enumerate(admitted):
                group = "source-" + admitted[find(i)][0][:20]
                bucket = int(hashlib.sha256(group.encode()).hexdigest()[:8],16) % 100
                split = "train" if bucket < 60 else "val_select" if bucket < 75 else "val_cal" if bucket < 85 else "test_id"
                rows.append({"id": "source-" + key[:24], "text": text, "label": "scam", "language": "en",
                    "family": family, "scenario_group_id": group, "parent_id": None,
                    "generation_batch_id": None, "source_id": "user-csv-unverified", "source_type": "user_provided",
                    "license_or_generation_method": "unknown; user requested local demonstration only",
                    "human_review_status": "unreviewed", "synthetic": False, "split": split,
                    "shift_type": "normal", "impersonation_target": "redacted", "requested_action": "unknown"})
        audit.update({"admitted_source_rows": len(admitted), "rejected": dict(reasons),
            "privacy": "Automated conservative masking; not proof of privacy review. Original CSV untouched and excluded from Git.",
            "label_assumption": "banking/delivery/government/telecom treated as source-annotated scam; spam/others excluded",
            "source_label_confound": "Imported data contain scams only; legitimate controls are synthetic. Metrics are not a field benchmark."})
    # Predetermined order: normal traffic, then unfamiliar scams interleaved with benign novelty.
    replay_rows = [r for r in rows if r["split"] == "shift_demo"]
    normal = [r for r in replay_rows if r["shift_type"] == "normal"]
    novel = [r for r in replay_rows if r["shift_type"] != "normal"]
    rng = random.Random(42)
    rng.shuffle(normal)
    rng.shuffle(novel)
    for index, row in enumerate(normal + novel):
        row["event_index"] = index
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    load_data(output, simulation=True)
    write_json(output.with_suffix(".audit.json"), audit)
    print(json.dumps({"output": str(output), "rows": len(rows), "counts": dict(Counter(r["split"] for r in rows))}))


if __name__ == "__main__":
    main()
