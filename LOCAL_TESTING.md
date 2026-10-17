# Test the full system locally

How to clone this repo and run the whole stack on your own machine: the API with the frozen model, plus the React analyst console. Then check it works end to end.

There are two ways to run it:

- **Path A: Docker.** One command; the closest match to the hosted setup.
- **Path B: no Docker.** Python and Node run directly on your machine. Use this if you don't have Docker, or if you want to run the test suite.

Both need **internet on first setup**, because the encoder weights (449 MB) and the dependencies are downloaded. After that, the model runs offline.

---

## 1. Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Git | any recent | both paths |
| Docker Desktop (Windows/macOS) or Docker Engine + Compose v2 (Linux) | Compose v2 (`docker compose`, not `docker-compose`) | Path A |
| Python | **3.12 exactly** (3.11 and 3.13 are not supported) | Path B, smoke test |
| Node.js | **20 or newer** (22 recommended) | Path B console |

Hardware: about **2 GB of free RAM** for the API and **3 GB of free disk**. On Docker Desktop, check that *Settings → Resources → Memory* is at least 4 GB.

Ports used: `8000` (API), `8080` (console in Docker), `5173` (console dev server). Free them first or the services won't start.

## 2. Clone the right branch

The console (`app/client`) is only on `feature/frontend` for now, so clone that branch:

```bash
git clone --branch feature/frontend https://github.com/Dilhara11/ScamFit-TnsorForge-Lumora.git
cd ScamFit-TnsorForge-Lumora
```

The repo is private, so Git will ask for your GitHub username and a personal access token (not your password).

> **Do not change line endings.** The API checks a SHA-256 hash of every model file and runtime source file at startup, and refuses to start if any byte differs. The repo's `.gitattributes` pins the right line endings for you, so a normal clone works on Windows, macOS and Linux.
>
> Don't run `git add --renormalize`, and don't let an editor "fix" line endings in `training/src/svo/` or `training/runs/`. If you cloned before `.gitattributes` was added, see [Troubleshooting](#7-troubleshooting).

---

## 3. Path A: Docker

From the repository root:

```bash
docker compose --profile frontend up --build -d --wait
```

The first build takes about 5–15 minutes: it downloads the Python image, PyTorch (CPU) and the encoder weights, then verifies the model. Later starts take seconds. `--wait` returns once both containers are healthy. The API can take up to 2 minutes to load the model.

Then open:

- Console: <http://127.0.0.1:8080>
- API docs: <http://127.0.0.1:8000/docs>
- Readiness: <http://127.0.0.1:8000/health/ready>

To start only the API, without the console, leave out `--profile frontend`.

Useful commands:

```bash
docker compose ps                 # both services should be "healthy"
docker compose logs -f api        # API logs
docker compose --profile frontend stop     # stop, keep data
docker compose --profile frontend down     # remove containers, keep data volume
docker compose --profile frontend down -v  # also delete stored predictions/reviews
```

Go on to [section 5](#5-check-that-it-works).

---

## 4. Path B: no Docker

Run every command from the **repository root**. Commands are given for Windows PowerShell and for macOS/Linux/Git Bash.

### 4.1 Python environment (once)

**Windows PowerShell**

```powershell
py -3.12 -m venv app/server/.venv
app\server\.venv\Scripts\python -m pip install --upgrade pip
app\server\.venv\Scripts\python -m pip install -r app/server/requirements-dev.lock
app\server\.venv\Scripts\python app/server/scripts/fetch_model_weights.py
```

**macOS / Linux / Git Bash**

```bash
python3.12 -m venv app/server/.venv
app/server/.venv/bin/python -m pip install --upgrade pip
app/server/.venv/bin/python -m pip install -r app/server/requirements-dev.lock
app/server/.venv/bin/python app/server/scripts/fetch_model_weights.py
```

In Git Bash on Windows the venv folder is `Scripts/`, not `bin/`, so use `app/server/.venv/Scripts/python`.

`fetch_model_weights.py` downloads `encoder/model.safetensors` from Hugging Face at the pinned revision, and refuses it if the hash doesn't match. Run it once per clone. It should print `"fetched": ["encoder/model.safetensors"]` the first time and `"fetched": []` after that.

### 4.2 Verify the model and run the tests

**Windows PowerShell**

```powershell
$env:PYTHONPATH = "app/server/src;training/src"
app\server\.venv\Scripts\python app/server/scripts/verify_runtime.py
app\server\.venv\Scripts\python -m pytest app/server/tests -q
```

**macOS / Linux / Git Bash**

```bash
export PYTHONPATH=app/server/src:training/src     # Git Bash on Windows: use ";" instead of ":"
app/server/.venv/bin/python app/server/scripts/verify_runtime.py
app/server/.venv/bin/python -m pytest app/server/tests -q
```

Expected result: `verify_runtime.py` succeeds, and pytest reports **15 passed, 1 skipped** in about 2 minutes. The skipped test is the live-server smoke test, which you can run later in section 5.

### 4.3 Start the API (terminal 1)

Keep this terminal open. `PYTHONPATH` must be set in it, as in 4.2.

```powershell
# Windows PowerShell
$env:PYTHONPATH = "app/server/src;training/src"
app\server\.venv\Scripts\python -m uvicorn svo_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

```bash
# macOS / Linux
PYTHONPATH=app/server/src:training/src app/server/.venv/bin/python -m uvicorn \
  svo_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Wait for `Application startup complete`, which takes about 10–45 seconds while PyTorch and the encoder load. Data is stored in `app/server/data/observatory.sqlite`, which Git ignores. Delete that file for a clean start.

### 4.4 Start the console (terminal 2)

```bash
cd app/client
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. The dev server forwards `/api` and `/health` to `127.0.0.1:8000`, so no CORS settings are needed.

---

## 5. Check that it works

Run these with the API up, from either path.

### 5.1 Automated smoke test

This test needs only the Python standard library, so any Python 3.12 install works, including the venv:

```bash
python app/server/scripts/smoke.py
```

It should print JSON with `"passed": true` and `"model_version": "svo-e2a46f504b19"`. The test scores a message, checks idempotent retries and `409` / `422` errors, and runs a review round-trip.

With Path B you can also run the smoke test through pytest:

```powershell
$env:SVO_TEST_URL = "http://127.0.0.1:8000"; app\server\.venv\Scripts\python -m pytest app/server/tests -q    # now 16 passed
```

### 5.2 Manual API check

```bash
curl http://127.0.0.1:8000/health/ready
curl -X POST http://127.0.0.1:8000/api/v1/predictions -H "Content-Type: application/json" -d "{\"text\":\"Your parcel is held. Pay the release fee at the link today.\",\"event_id\":\"manual-001\"}"
```

In PowerShell, use `curl.exe` rather than `curl`. The response should include `scam_score`, `decision`, `novelty_score` and `cluster_id_or_null`. If you send the same body again, you get the same response back. If you reuse `manual-001` with different text, you get `409`.

### 5.3 Console walkthrough

1. **Overview** loads with no error banner, and the sidebar badge says **Local demo mode**.
2. **Scan messages**: score one scam-like message and one ordinary message, such as "The office opens tomorrow." The scam-like one should be routed to review or high risk. The ordinary one should be low risk.
3. **Scan messages → Batch replay**: paste several similar scam messages, one per line, and click **Run batch**. A cluster should appear.
4. **Variant queue**: open the cluster and submit a review (confirm or reject). It should appear in the audit trail.
5. **Model & limits**: shows `e5_tfidf`, the frozen thresholds and the limitations.

All test messages are stored only as hashes and scores on the server. The console keeps its own copy of the text in your browser, which you can clear under **Connection**.

---

## 6. Optional: test authenticated mode

By default the API runs in `local_demo` mode, with no key and loopback only. To test API keys locally, create a `.env` file in the repo root. Git already ignores it.

```dotenv
SVO_MODE=authenticated
SVO_CREDENTIALS_JSON={"analyst-1":"replace-with-a-random-string-of-at-least-32-chars"}
```

Then run `docker compose --profile frontend up -d --wait --force-recreate`. For Path B, set the same two variables in the API terminal before starting uvicorn.

Once it's running:

- Requests without a key get `401`.
- In the console, open **Connection** and enter the key.
- For the smoke test, set the key first: `SVO_API_KEY=<key> python app/server/scripts/smoke.py`. In PowerShell: `$env:SVO_API_KEY="<key>"`.

Keys must be unique ASCII strings of at least 32 characters, or the API refuses to start. Never commit `.env`.

---

## 7. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| API exits at startup or the Docker build fails in `verify_runtime.py` with a source/manifest hash error | Line endings in `training/src/svo/*.py` changed. Run `git pull` to get `.gitattributes`, then `git rm -r --cached training/src/svo` and `git checkout -- training/src/svo` (only if you have no local edits there), and retry. |
| `Downloaded encoder/model.safetensors does not match the bundle manifest` | The download was interrupted or altered, for example by a corporate proxy. Delete any `.fetch-*` folder beside the bundle and rerun `fetch_model_weights.py`, or rebuild. |
| Build fails reaching `huggingface.co` or PyPI | The first build needs internet. Check your proxy/VPN, then retry. |
| `docker compose up --wait` times out or the API container restarts | Usually too little memory. Give Docker at least 4 GB, then check `docker compose logs api`. |
| Docker on Windows/WSL: `docker version` shows no server, or there's a builder/bind-mount error | Start Docker Desktop and enable WSL integration. If a custom builder fails, run `docker buildx use default`. |
| `pip install` fails resolving `torch==...+cpu` or other pins | You're not on Python 3.12, or not on 64-bit Python. Recreate the venv with Python 3.12 x64. |
| `ModuleNotFoundError: svo_api` or `svo` | `PYTHONPATH` isn't set in that terminal, or you're not in the repo root. On Windows the separator is `;`. |
| `database is locked` / the engine refuses to start | Another API process (or the Docker container) already uses the same database. Stop it, because only one engine per database is allowed. |
| Port already in use | Something is already listening on 8000, 8080 or 5173. Stop it, or stop the other path (Docker vs local), which uses the same ports. |
| Console shows connection or loading errors | The API isn't ready yet (wait for `/health/ready`), or the console's **Connection** base URL was changed. Clear it so the console uses the same origin. |
| `429` responses during a large batch | The engine queue is full (32 by default). The console retries automatically. This is expected under load. |

## 8. Limits to keep in mind while testing

- This is a demonstration model. Held-out macro-F1 is 0.932, but high-risk precision is 83.2%, below the 90% target. "Low risk" does not mean safe. See [training/RESULTS_V2.md](training/RESULTS_V2.md).
- Novelty is a distance signal, not a fraud probability. A cluster appears only after recurring similar reports.
- Requests are handled by one engine thread, so predictions queue. Expect a few hundred ms per prediction on a laptop CPU.

More detail: [app/server/README.md](app/server/README.md) (API contract, operations), [app/client/README.md](app/client/README.md) (console), [DEPLOY.md](DEPLOY.md) (AWS).
