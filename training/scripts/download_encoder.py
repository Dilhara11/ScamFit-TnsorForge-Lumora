"""Download only needed E5 files and pin the resolved hub commit."""
import argparse
import json
from pathlib import Path


def main():
    from huggingface_hub import HfApi, snapshot_download
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="training/cache/multilingual-e5-small")
    args = parser.parse_args()
    repo = "intfloat/multilingual-e5-small"
    revision = HfApi().model_info(repo).sha
    snapshot_download(repo, revision=revision, local_dir=args.output,
        allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors", "1_Pooling/*", "README.md", "LICENSE*"])
    path = Path(args.output)
    (path / "revision.json").write_text(json.dumps({"repo": repo, "revision": revision, "license": "MIT"}, indent=2))
    print(json.dumps({"path": str(path), "revision": revision}))


if __name__ == "__main__":
    main()
