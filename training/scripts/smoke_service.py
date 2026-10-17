"""Exercise the real local HTTP service using development data only."""
import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from svo.data import write_json
from svo.model import Runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    runtime = Runtime(args.bundle)
    development = [json.loads(line) for line in Path(args.data).read_text().splitlines()
                   if json.loads(line)["split"] == "val_select"]
    # Verify real language/batch parity without recording text in test evidence.
    fixtures = [next(r for r in development if r["language"] == language)
                for language in sorted({r["language"] for r in development})]
    batch = runtime.predict_vectors([r["text"] for r in fixtures])[0]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    def request(path, obj=None):
        req = urllib.request.Request(base + path, data=None if obj is None else json.dumps(obj).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)
    checks = []
    with tempfile.TemporaryDirectory(prefix="svo-smoke-") as tmp:
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
        process = subprocess.Popen([sys.executable, "-m", "svo.serve", "--bundle", args.bundle,
                                    "--db", str(Path(tmp)/"service.sqlite"), "--port", str(port)],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError("Service startup failed: " + process.communicate()[1][-2000:])
                try:
                    status, health = request("/health")
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise TimeoutError("Service startup timeout")
            assert status == 200 and health["model_version"] == runtime.version
            checks.append("health_matches_loaded_version")
            cluster_id = None
            for i,(row,expected) in enumerate(zip(fixtures, batch)):
                status, response = request("/predict", {"text": row["text"], "event_id": f"fixture-{i}"})
                assert status == 200
                assert abs(response["scam_score"] - expected["scam_score"]) < 1e-6
                assert response["decision"] == expected["decision"]
                assert response["is_unknown"] == expected["is_unknown"]
                if response["cluster_id_or_null"] is not None:
                    cluster_id = response["cluster_id_or_null"]
                checks.append("http_batch_parity_" + row["language"])
            status, repeat = request("/predict", {"text": fixtures[0]["text"], "event_id": "fixture-0"})
            assert status == 200
            checks.append("idempotent_repeat")
            assert request("/predict", {"text": "Different request", "event_id": "fixture-0"})[0] == 400
            assert request("/predict", {"text": " "})[0] == 400
            assert request("/predict", {"text": 12})[0] == 400
            assert request("/predict", {"text": "a"*10001})[0] == 400
            checks.append("invalid_and_conflicting_inputs_rejected")
            status, state = request("/status")
            assert status == 200 and state["monitoring"] == "insufficient observations"
            checks.append("insufficient_observations_reported")
            if cluster_id is not None:
                status, result = request("/review", {"cluster_id": cluster_id, "status": "rejected", "actor": "smoke-test"})
                assert status == 200 and result["automatic_retraining"] is False
                checks.append("analyst_response_persisted_without_retraining")
            assert request("/review", {"cluster_id": 99999, "status": "rejected", "actor": "smoke-test"})[0] == 400
            checks.append("unknown_cluster_rejected")
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    write_json(args.output, {"version": runtime.version, "checks": checks, "passed": len(checks),
                             "fixture_partition": "val_select", "offline_hub": True})
    print(json.dumps({"passed": len(checks), "version": runtime.version}))


if __name__ == "__main__":
    main()
