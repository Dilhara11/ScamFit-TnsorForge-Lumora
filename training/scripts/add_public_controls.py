"""Add real legitimate SMS (UCI SMS Spam Collection, CC BY 4.0, "ham" only) to a
prepared dataset. Writes a new file; the input dataset is never modified.

Why: v1 had six independent legitimate training scenarios, all synthetic, and
every real message was a scam. UCI ham gives real legitimate traffic, so source
no longer determines the label. UCI "spam" is not fraud and is not used.
"""
import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from svo.data import digest, load_data, write_json
from svo.preprocessing import text_hash
from svo.v2 import scrub


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="training/data/processed/messages.jsonl")
    p.add_argument("--uci", default="training/data/external/uci_sms/SMSSpamCollection")
    p.add_argument("--output", default="training/data/processed/messages_v2.jsonl")
    p.add_argument("--limit", type=int, default=1000)
    args = p.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Refusing to overwrite a prepared dataset; use a new output path")
    rows = [json.loads(l) for l in Path(args.base).read_text(encoding="utf-8").splitlines() if l.strip()]
    seen = {text_hash(r["text"]) for r in rows}
    ham = [line.split("\t", 1)[1] for line in Path(args.uci).read_text(encoding="utf-8").splitlines()
           if line.startswith("ham\t")]
    random.Random(42).shuffle(ham)
    admitted, reasons = [], Counter()
    for raw in ham:
        try:
            # Same masking the imported CSV received, so ham looks like real masked traffic.
            text = scrub(raw)
        except ValueError:
            reasons["invalid_text"] += 1
            continue
        if len(text) < 20 or len(text) > 800:
            reasons["length"] += 1
            continue
        key = hashlib.sha256(re.sub(r"[^a-z ]", "", text.lower()).encode()).hexdigest()
        if key in seen or text_hash(text) in seen:
            reasons["duplicate_template"] += 1
            continue
        seen.update({key, text_hash(text)})
        admitted.append((key, text))
        if len(admitted) >= args.limit:
            break
    # Consolidate near-duplicates into one group before any split, as prepare_data does.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neighbors import NearestNeighbors
    x = TfidfVectorizer(analyzer="char", ngram_range=(3, 5), max_features=30000).fit_transform([a[1] for a in admitted])
    near = NearestNeighbors(metric="cosine", radius=.25).fit(x).radius_neighbors(x, return_distance=False)
    parent = list(range(len(admitted)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, js in enumerate(near):
        for j in js:
            parent[find(int(j))] = find(i)
    for i, (key, text) in enumerate(admitted):
        group = "uci-ham-" + admitted[find(i)][0][:20]
        bucket = int(hashlib.sha256(group.encode()).hexdigest()[:8], 16) % 100
        split = "train" if bucket < 60 else "val_select" if bucket < 75 else "val_cal" if bucket < 85 else "test_id"
        rows.append({"id": "uci-" + key[:24], "text": text, "label": "legitimate", "language": "en",
            "family": "legitimate_public_sms", "scenario_group_id": group, "parent_id": None,
            "generation_batch_id": None, "source_id": "uci-sms-spam-collection-ham",
            "source_type": "public_dataset",
            "license_or_generation_method": "CC BY 4.0; Almeida & Gomez Hidalgo, UCI ML Repository (2011)",
            "human_review_status": "unreviewed", "synthetic": False, "split": split,
            "shift_type": "normal", "impersonation_target": "none", "requested_action": "none"})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")
    load_data(output, simulation=True)
    audit = {"base": str(args.base), "base_sha256": digest(args.base), "uci_sha256": digest(args.uci),
             "uci_ham_rows": len(ham), "admitted": len(admitted),
             "admitted_groups": len({find(i) for i in range(len(admitted))}), "rejected": dict(reasons),
             "label_meaning": "UCI ham = ordinary personal SMS; not bank/service notifications",
             "residual_confound": "Real legitimate SMS are informal chat; formal legitimate notices remain synthetic only"}
    write_json(output.with_suffix(".audit.json"), audit)
    print(json.dumps({"output": str(output), "rows": len(rows), **audit,
                      "counts": {f"{s}|{l}": n for (s, l), n in Counter((r["split"], r["label"]) for r in rows).items()}}))


if __name__ == "__main__":
    main()
