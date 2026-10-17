import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from svo.artifacts import verify_bundle

p = argparse.ArgumentParser()
p.add_argument("bundle")
args = p.parse_args()
manifest = verify_bundle(args.bundle)
print(json.dumps({"verified": True, "version": manifest["version"], "files": len(manifest["files"])}))
