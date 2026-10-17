# Scam Variant Observatory API

A separate FastAPI service around the frozen character TF-IDF classifier. It provides predictions, persistent rolling novelty monitoring, a cluster queue, and audited analyst reviews. Training files and model thresholds are unchanged.

## Run

From the repository root, with Docker Desktop/Engine and Compose available:

```bash
docker compose up --build -d --wait
```

The API is at `http://127.0.0.1:8000`; health is `/health/ready`, offline documentation is `/docs`, and the machine-readable contract is `/openapi.json`. The first build downloads a pinned Python image and dependencies; running inference needs no internet. Compose uses host-loopback port publication, a non-root user, and a read-only root filesystem. It uses the standard bridge for host access; inference also passes a separate test with Docker networking disabled. The image contains no training dataset, caches, virtual environment, or evaluation database.

The selected model bundle is included in the repository at `training/runs/final/bundle/` and is copied into the image during the build. A clone containing the bundle needs no retraining or separate model download. Keep the repository and image private while data provenance/licensing remains unresolved. Checksums verify integrity, not who produced the joblib artifact.

If Docker Desktop was just enabled in WSL, confirm `docker version` shows both client and server. If an old custom builder reports a missing WSL bind mount, use `BUILDX_BUILDER=default docker compose up --build -d --wait` or select a working builder with `docker buildx use default`.

```bash
python3 app/server/scripts/smoke.py
curl -s http://127.0.0.1:8000/api/v1/predictions \
  -H 'Content-Type: application/json' \
  -d '{"text":"The office opens tomorrow.","event_id":"example-001"}'
docker compose logs -f api
docker compose stop
docker compose up -d --wait
```

## API

| Route | Purpose |
|---|---|
| `GET /health/live` | Public process health |
| `GET /health/ready` | Public readiness and actual model version |
| `GET /api/v1/model` | Frozen configuration, deployment mode, limitations |
| `POST /api/v1/predictions` | Score and record one message |
| `GET /api/v1/monitoring` | Event count, latest window, cluster summary, disk space |
| `GET /api/v1/clusters` | Cluster queue; `status`, `limit`, `after_id` filters |
| `GET /api/v1/clusters/{id}` | Cluster details and up to five representative event IDs |
| `POST /api/v1/clusters/{id}/reviews` | Audited analyst decision |
| `GET /api/v1/clusters/{id}/reviews` | Audit history; `limit`, `after_id` pagination |

Requests reject extra fields and implicit type conversions. Prediction text is 1–10,000 characters, must not be blank, and follows the frozen Unicode normalization. IDs are 1–128 characters drawn from `A-Z a-z 0-9 . _ ~ -`. Bodies must be uncompressed UTF-8 JSON, at most 64 KiB on the wire, with a 10-second body-read deadline. JSON escaping counts toward the byte limit. Query page limits are 1–100; cursors are nonnegative IDs; a null `next_after_id` marks the end.

Example review body:

```json
{"review_id":"review-001","status":"rejected","actor":"local-analyst"}
```

Status is `pending`, `confirmed`, or `rejected`. `actor` is optional and explicitly unverified in local mode. Omit it in authenticated mode: the service derives it from credentials. Confirmation never automatically trains or approves training data.

A retry with the same event ID and normalized text/model returns the original stored prediction. Conflicting reuse returns `409`; IDs remain reserved across versions. Different IDs for the same normalized text add reports without increasing unique-text recurrence within a cluster. Review IDs are also durable and idempotent; conflicting body, actor, or model reuse returns `409`. Disconnecting does not cancel accepted mutations, so retry using the same ID.

Responses preserve the training fields including `scam_score`, `decision`, `needs_review`, `novelty_score`, `is_unknown`, `nearest_known_family_or_null`, `cluster_id_or_null`, versions, and scope. `cluster_capacity_reached` is always a boolean. `low_risk` is not verified safety. Novelty is lexical distance, not fraud probability or confirmed concept drift. Representative event IDs let a private client find its own source evidence; the server stores no raw messages.

Errors use `{"error":{"code":"...","message":"...","request_id":"..."}}` and an `X-Request-ID` header. Codes: 400 malformed JSON, 401 invalid credentials, 404 unknown resource, 408 body timeout, 409 ID conflict, 413 size limit, 415 media type/encoding, 422 schema mismatch, 429 full engine queue, 503 unavailable engine/storage, 500 unexpected failure. Validation errors and logs do not echo message text.

## Authentication and frontend access

Default `local_demo` needs no key and publishes only to host loopback. Do not expose that mode through a tunnel, proxy, shared network, or LAN port. For nonlocal use choose `authenticated`, inject unique random keys of at least 32 ASCII characters, and terminate TLS at your deployment proxy. Do not place keys in source, URLs, screenshots, browser builds, or public logs.

Settings can be injected through the environment or a private root `.env` file (ignored by Git). `SVO_CREDENTIALS_JSON` is a JSON mapping of analyst alias to secret key. Supply it using a secret store or protected environment; do not put actual keys in shell command examples. Compose does not enforce outbound filtering. For hosted isolation, apply your infrastructure egress policy; the application makes no runtime network calls.

| Setting | Default / meaning |
|---|---|
| `SVO_MODE` | `local_demo` or `authenticated` |
| `SVO_CREDENTIALS_JSON` | `{}`; required in authenticated mode |
| `SVO_ALLOWED_ORIGINS` | Empty; comma-separated exact frontend origins |
| `SVO_QUEUE_CAPACITY` | 32 waiting operations |
| `SVO_MODEL_DIR` | `/opt/model` in container |
| `SVO_EXPECTED_MODEL_VERSION` | `svo-38879254a924` |
| `SVO_DB_PATH` | `/data/observatory.sqlite` in container |

Clients send `X-API-Key` or `Authorization: Bearer …`. All API and documentation endpoints require credentials in authenticated mode; health remains public. CORS preflight may be unauthenticated, while actual requests require credentials. CORS is disabled unless explicitly configured. No threshold overrides are supported.

## Persistence, lifecycle, and backup

One Uvicorn process owns one bounded FIFO queue and one engine thread. That thread owns the runtime and SQLite connection. A file lock prevents two engine processes sharing the same database. Do not scale replicas or workers against the same volume. Health stays on the HTTP event loop. Shutdown stops new engine work and drains accepted operations for up to 25 seconds; Compose allows 35 seconds before killing the container. Work still uncommitted after forced termination can be retried with the same IDs.

SQLite WAL data lives in the named `svo-data` volume; `docker compose down` preserves it. No automatic metadata expiry is implemented because removing records changes idempotency and monitoring history. Watch `disk_free_bytes` in monitoring; below a 16 MiB reserve or after a storage write failure, readiness becomes unavailable and engine work is rejected until repair and restart. Prediction/cluster/window effects and review/audit effects are transactionally persisted. Model versions isolate monitoring state; event IDs remain globally unique.

Create a consistent live backup inside the volume:

```bash
docker compose exec api python scripts/backup.py /data/observatory.sqlite /data/backup.sqlite
docker compose cp api:/data/backup.sqlite ./observatory-backup.sqlite
```

The backup command refuses to overwrite an existing file. Store backups privately. To restore, stop the API, mount its named volume in a maintenance container, preserve the current database/WAL/SHM as a separate recovery copy, replace the database with the backup, remove stale WAL/SHM belonging to the replaced database, and restore UID/GID 10001 ownership before startup. Never copy just the live main database file. Do not run `docker compose down -v` unless deliberately deleting all service state.

For rollback retain the previous image ID/tag and a compatible database backup. Schema version 1 is additive; a newer unsupported schema fails startup. Use the prior image and its compatible backup, then run smoke checks. No hot model replacement is supported.

## Development and verification

From the repository root:

```bash
python3 -m venv app/server/.venv
app/server/.venv/bin/python -m pip install -r app/server/requirements-dev.lock
PYTHONPATH=app/server/src:training/src app/server/.venv/bin/python -m pytest app/server/tests -q
PYTHONPATH=app/server/src:training/src app/server/.venv/bin/python app/server/scripts/verify_runtime.py
# Local development; bind to loopback explicitly:
PYTHONPATH=app/server/src:training/src app/server/.venv/bin/python -m uvicorn \
  svo_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
# With Compose already running:
SVO_TEST_URL=http://127.0.0.1:8000 app/server/.venv/bin/python -m pytest app/server/tests -q
python3 app/server/scripts/benchmark.py
```

`SVO_API_KEY` supplies a key to the smoke/benchmark scripts for authenticated mode. Tests use temporary databases and include the private shifted replay if supplied. They never retrain, retune thresholds, or rerun held-out model evaluation. Smoke and benchmarks add harmless demonstration events to the service database; use a fresh Compose project/volume for isolated measurements. See `VERIFICATION.md` for measured results and remaining limits.

The API loads resources through FastAPI's [lifespan interface](https://fastapi.tiangolo.com/advanced/events/). All copied `svo` modules must match manifest source hashes before loading the model. API dependencies and the base-image digest are pinned; CPU-only ML versions match the training runtime. `requirements.in` and `requirements-dev.in` describe lock inputs.

## Model limitations

This is an unreviewed mixed-source demonstration. Scores are uncalibrated and Sinhala/Tamil evidence is weak. Held-out high-risk recall is 69.4%, review workload is 100%, and normal replay false-alert windows are 11.1%. No cluster met the candidate rule at the end of the reported replay. `operating_target_met` in the frozen config refers to development selection, not held-out success. No real-world fraud protection, reliable emerging-variant discovery, or workload reduction is claimed. See `training/RESULTS.md` and the model card for full context.
