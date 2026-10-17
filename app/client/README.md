# Scam Variant Observatory console

React + Tailwind analyst console for the API in `app/server/`. It covers the problem statement's detect → monitor → respond loop:

| Page | Purpose | API |
|---|---|---|
| Overview | Drift alert, unfamiliar-message rate per window, queue counts, candidate variants | `GET /api/v1/monitoring`, `GET /api/v1/clusters` |
| Scan messages | Score one message, or replay a batch in order to exercise drift monitoring | `POST /api/v1/predictions` |
| Variant queue | Clusters filtered by review status, candidates only, sortable, cursor pagination | `GET /api/v1/clusters` |
| Cluster detail | Progress toward the candidate rule, representative reports, analyst decision, audit trail | `GET /api/v1/clusters/{id}`, `POST/GET …/reviews` |
| Model & limits | Frozen thresholds, monitoring settings, deployment mode, limitations | `GET /api/v1/model` |

## Run

Development (Node 20+), with the API running on `127.0.0.1:8000`:

```bash
cd app/client
npm install
npm run dev          # http://127.0.0.1:5173
```

The dev server proxies `/api` and `/health` to the API, so the browser sees one origin and `SVO_ALLOWED_ORIGINS` can stay empty. Point the proxy elsewhere with `SVO_API_PROXY_TARGET=http://host:port npm run dev`.

Container (from the repository root). The client is behind a Compose profile so the default API-only startup is unchanged:

```bash
docker compose --profile frontend up --build -d --wait   # http://127.0.0.1:8080
```

nginx serves the static build and proxies `/api` and `/health` to the `api` service on the same origin.

`npm run build` type-checks and writes `dist/`. `npm run typecheck` only type-checks.

## Design decisions

- **Scores read against thresholds.** Scam score and novelty are drawn on scales with the frozen thresholds from `/api/v1/model`, so a number is never shown without the boundary that produced its decision. Score and novelty stay visually separate because they mean different things.
- **Low risk is not green.** Decisions use rose / amber / neutral slate, always with an icon and label. A "safe" colour would overstate what the model knows.
- **Wording follows the model.** Calibration status and novelty type (lexical for TF-IDF) come from `/api/v1/model`. The UI does not hardcode them, so a model change does not leave stale claims on screen.
- **Idempotent retries.** Each scan and review gets a client ID (`web-…`, `batch-…`, `review-…`). After a network error, timeout, 429 or 5xx, retrying reuses the same ID, so a report is never counted twice. A 429 response is retried automatically after `Retry-After`. Editing the text starts a new ID.
- **Batch replay is sequential.** Monitoring windows depend on report order, so batch lines are sent one at a time, in order. Failed lines can be retried with their original IDs.
- **Evidence stays on the device.** The server never stores message text. To let analysts read cluster members, the browser keeps its own copy of what it submitted, keyed by event ID, in `localStorage`. This can be turned off or cleared under **Connection**. Other devices' reports show as event IDs only.
- **Window trend is a session view.** The API exposes only the latest window, so the chart plots the windows this browser has seen. The UI says so.
- **No secrets in the bundle.** In authenticated mode, enter an API key under **Connection**. It is kept in `sessionStorage` for that tab and sent as `X-API-Key`. In local demo mode the analyst alias is recorded as unverified.
- **Accessible.** Uses semantic landmarks, `role="meter"` on scales, `aria-live` results, visible focus rings and reduced-motion support. Layouts were checked at 360 px with no horizontal scroll.

## Structure

```text
src/
  api/          types.ts mirrors svo_api/schemas.py; client.ts handles the error envelope
  lib/          connection settings, IDs, local evidence, polling hooks, observatory context
  components/   layout, UI primitives, score scales and window chart, prediction result
  pages/        Overview, Scan, Variants, VariantDetail, Model
```
