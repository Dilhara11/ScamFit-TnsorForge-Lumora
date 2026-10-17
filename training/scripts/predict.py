import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from svo.model import Runtime

p = argparse.ArgumentParser()
p.add_argument("--bundle", required=True)
p.add_argument("--text", required=True)
args = p.parse_args()
print(json.dumps(Runtime(args.bundle).predict(args.text), indent=2, ensure_ascii=False))
