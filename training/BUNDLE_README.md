# Offline runtime bundle

Keep this archive private: the supplied training CSV has unknown provenance and
licensing, and the multilingual synthetic data are unreviewed. This is a demo.

From the extracted ZIP directory, create a Python 3.12 virtual environment and
install `requirements-runtime.txt`. If `bundle/manifest.json` says candidate
`e5`, install `requirements-training.txt` instead (includes CPU PyTorch).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-runtime.txt
# For an E5 bundle:
# .venv/bin/python -m pip install -r requirements-training.txt
PYTHONPATH=src .venv/bin/python -c 'from svo.artifacts import verify_bundle; print(verify_bundle("bundle")["version"])'
PYTHONPATH=src .venv/bin/python -m svo.serve --bundle bundle --db service.sqlite
```

The API listens on `127.0.0.1:8000`. `GET /health`, `GET /status`, `POST /predict`
with JSON `{"text":"The office opens tomorrow."}` and `POST /review` with
`{"cluster_id":1,"status":"rejected","actor":"analyst-alias"}` are available.
The service verifies file hashes before loading and does not contact the hub.
Use only a trusted team-generated bundle; hashes are not publisher signatures.
Scores are uncalibrated. Low risk is not proof of safety; novelty is not fraud.
