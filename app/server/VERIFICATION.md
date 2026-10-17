# API engine verification

## v2 engine (`svo-e2a46f504b19`, `e5_tfidf`) — 2026-10-17

Verified on the Windows 11 development host (Python 3.12.10, CPU), not in Docker. Docker is not installed on that host, so **the image build, `docker compose up --wait`, the read-only/non-root container, and `--network none` startup have not been re-verified for v2**. Run those before relying on the container.

| Check | Result |
|---|---|
| API suite (`pytest app/server/tests`) against the v2 bundle | **15 passed, 1 skipped** (container smoke needs `SVO_TEST_URL`), 112 s |
| Prediction and ordered monitoring parity, multilingual fixtures and private v2 shift replay | Passed (API output equals frozen runtime) |
| Windows-sealed manifest (backslash paths) verifies; traversal via `..\` rejected; tampering rejected | Passed |
| Representation allowlist (`tfidf_char_raw` refused); `v2.py` source hash enforced | Passed |
| Real HTTP smoke (`scripts/smoke.py`) against local Uvicorn on 127.0.0.1 | **Passed** |
| `/api/v1/model` | Reports `e5_tfidf`, `scores_calibrated: true`, v2 held-out limitations |
| Dev lock install (`requirements-dev.lock`, clean venv) | Passed |
| Engine startup to ready (local Uvicorn, warm disk cache) | ~10 s; cold first import measured up to ~26–45 s, hence the 120 s healthcheck start period |
| Resident memory after load + 200 predictions | **~1.19 GB (peak 1.23 GB)**: exceeds the old 1 GiB limit; Compose now allows 2 GiB |
| Prediction HTTP p50 / p95 / max, concurrency 4, 200 samples | 281 / 336 / 443 ms on this host (single engine thread, so requests queue; host was under heavy memory pressure). v1 measured 29 / 33 ms in the Linux container. Not directly comparable; re-measure in the container |

Changes behind these results: portable manifest verification and one verified load (`load_runtime`); representation allowlist with per-representation source modules; metadata taken from the bundle instead of hard-coded TF-IDF claims; a portable single-writer lock (fcntl or msvcrt); E5 inference dependencies in the locks; `v2.py` and the v2 bundle in the image; offline Hugging Face settings; fixtures that need a cluster now use a review-routed message, because v2 correctly sends ordinary text to low risk.

The v1 results below and `verification.json` describe the previous image and model and are kept as historical evidence.

## v1 engine (`svo-38879254a924`)

Verified on 2026-10-17 using Docker Desktop 4.94.0, Docker Engine 29.8.2, Compose 5.5.1, and WSL2 Linux x86_64. The container benchmark profile was capped at 2 CPUs and 1 GiB memory. These are local demonstration results, not a production capacity claim.

## Identity

- Model: `svo-38879254a924`, frozen TF-IDF + logistic regression.
- Image: `sha256:831d244337e7c3190e6bf947e1a084e2573affda9fc9e57a7ee3a72561173437` (`svo-api:local` at verification time).
- Base: `python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`.
- Container Python: 3.12.15; host test Python: 3.12.3.
- FastAPI: 0.143.3; scikit-learn: 1.9.1; complete runtime dependency pins: `requirements.lock`.
- Database schema: 1.
- Shared runtime modules pass the selected artifact's source hashes before load; trained artifact and training source were not modified.
- Source/lock hashes and result summary: `verification.json`.

## Results

| Check | Result |
|---|---|
| API suite including real HTTP container smoke | **14 passed**, 4.63 seconds |
| Docker build and `docker compose up --build -d --wait` | Passed; healthy container |
| New named volume initialization as non-root | Passed |
| Host endpoint | `127.0.0.1:8000`, real HTTP smoke passed |
| Model/source verification in build and startup | Passed |
| Prediction and ordered monitoring parity | Exact outputs match frozen runtime on multilingual fixtures and supplied private shifted replay |
| Concurrent identical event IDs | One event, identical responses, no duplicated monitoring effects |
| Review retries and conflicting IDs | Idempotent retry; conflicts return 409 |
| Fault injection during prediction/review writes | Rollback leaves no partial cluster/review changes |
| Restart persistence | Original event and review survive; retry preserves count |
| SQLite live backup | Integrity check `ok`; 102 events at backup time |
| Backup restoration | Tested using restored temporary database and idempotent prediction |
| Model-version isolation | Tested; old event ID reuse conflicts |
| Two engine processes on same database | Second process refuses startup |
| No raw text in stored records | Checked against SQLite dump |
| Authentication, validation, CORS, streaming body limit | Passed |
| Queue saturation and client cancellation | 429 on saturation; accepted mutation persists after caller cancellation |
| Storage failure | 503 readiness/operations, liveness remains available |
| Offline container (`--network none`) | Startup and real loopback HTTP prediction/review smoke passed |
| Offline readiness time | **2.258 s**, excludes build/image transfer |
| Prediction HTTP p50 / p95 / max | **28.641 / 32.645 / 35.450 ms** |
| Health HTTP p50 / p95 / max during load | **2.841 / 5.732 / 5.987 ms** |
| Container idle memory after restart | Approximately **101 MiB / 1 GiB** |
| Runtime privilege / immutable model | UID 10001; model not writable |
| Training-only dependency exclusion | PyTorch absent |
| Build context | Approximately 573 KiB on initial build; explicit source/bundle allowlist |

Latency used 100 harmless short-message predictions at concurrency 4 and 20 health probes. These warm measurements do not cover maximum-length messages, a full 100-cluster queue, sustained load, other CPU architectures, or hosted TLS. The smoke/benchmark added harmless demonstration events to the persistent local volume. They did not change training/evaluation artifacts or tune model thresholds.

## Environment issues resolved and remaining limits

- Docker initially lacked WSL integration; the user enabled it during implementation.
- The previously selected `tf-multi` builder contained a stale WSL bind mount. Selected the working `default` builder; standard Compose startup then worked.
- An internal-only Compose network suppressed host port publication on this Docker setup. Standard bridge networking now provides loopback host access. Offline behavior is verified separately with `--network none`; default Compose does not promise egress blocking.
- Sandboxed ASGI tests stalled on event-loop communication; the same suite passed outside the sandbox. The stalled test processes were stopped.
- One upstream test-client deprecation warning recommends `httpx2`; the pinned `httpx` test path currently passes. Production runtime does not depend on either test HTTP client.
- Authentication is exercised by API contract tests; no public deployment, TLS configuration, or live credential distribution was performed.
- `/docs` is an offline documentation entry page with an OpenAPI link, not a CDN-dependent interactive Swagger UI.
- Retention is manual. Long-term metadata growth, public rate limiting, multitenancy, multi-replica database ownership, and verified message-evidence storage remain outside this first release.
- Existing model-quality limitations remain unchanged; see `training/RESULTS.md`.

No files were staged or committed.
