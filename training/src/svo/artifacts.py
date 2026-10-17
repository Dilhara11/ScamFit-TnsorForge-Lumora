import hashlib
import json
from pathlib import Path

from .data import digest, write_json


def seal_bundle(bundle, metadata):
    bundle = Path(bundle)
    files = {str(p.relative_to(bundle)): digest(p) for p in sorted(bundle.rglob("*"))
             if p.is_file() and p.name != "manifest.json"}
    content = {**metadata, "files": files, "format_version": 1}
    content["version"] = "svo-" + hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()).hexdigest()[:12]
    write_json(bundle / "manifest.json", content)
    return content


def verify_bundle(bundle):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle / "manifest.json").read_text())
    unsigned = {k: v for k, v in manifest.items() if k != "version"}
    expected = "svo-" + hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest()[:12]
    if manifest["version"] != expected:
        raise ValueError("Manifest content/version mismatch")
    if not {"model.joblib", "decision_config.json", "model_card.md"} <= manifest["files"].keys():
        raise ValueError("Incomplete artifact manifest")
    for name, checksum in manifest["files"].items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle) or not path.is_file() or digest(path) != checksum:
            raise ValueError(f"Artifact hash mismatch/missing file: {name}")
    return manifest
