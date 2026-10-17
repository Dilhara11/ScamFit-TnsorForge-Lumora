"""Restore encoder files that are too large for Git into a bundle, then verify them.

The bundle manifest records the pinned hub revision and the SHA-256 of every file.
Missing encoder files are downloaded at exactly that revision and must match the
manifest hash, so the restored bundle is the same frozen, evaluated artifact.
Usage: python fetch_model_weights.py [BUNDLE_DIR]   (needs network; stdlib + huggingface_hub)
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    bundle = Path(sys.argv[1] if len(sys.argv) > 1 else os.getenv('SVO_MODEL_DIR', 'training/runs/v2/candidates/e5_tfidf/bundle'))
    manifest = json.loads((bundle / 'manifest.json').read_text())
    files = {name.replace('\\', '/'): checksum for name, checksum in manifest['files'].items()}
    # Hub metadata under .cache is shipped in Git; only real repository files are fetched.
    missing = [n for n in files if n.startswith('encoder/') and '/.cache/' not in f'/{n}'
               and not (bundle / n).is_file()]
    if not missing:
        print(json.dumps({'bundle': str(bundle), 'fetched': []}))
        return
    revision = (manifest.get('encoder_revision') or {})
    if not revision.get('repo') or not revision.get('revision'):
        raise SystemExit('Bundle has missing encoder files but no pinned encoder revision')
    from huggingface_hub import hf_hub_download
    # Download beside the bundle: same filesystem (atomic replace), not a small system temp.
    with tempfile.TemporaryDirectory(dir=bundle.resolve().parent, prefix='.fetch-') as tmp:
        for name in missing:
            source = hf_hub_download(revision['repo'], name[len('encoder/'):], revision=revision['revision'], local_dir=tmp)
            if sha256(source) != files[name]:
                raise SystemExit(f'Downloaded {name} does not match the bundle manifest')
            target = bundle / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, str(target) + '.partial')
            os.replace(str(target) + '.partial', target)
    print(json.dumps({'bundle': str(bundle), 'revision': revision['revision'], 'fetched': missing}))


if __name__ == '__main__':
    main()
