# One-hour training execution plan

This is the executable replacement for the original four-hour plan. The user's
one-hour budget controls this work even though the machine clock initially showed
09:27 Asia/Colombo and the competition document says 14:00. All implementation,
data, environments, models, evidence and exports live under `training/`.
No staging, commits, pushes or submission actions are permitted in this session.

| Minutes | Work | Exit evidence |
|---|---|---|
| 0–10 | Inspect source/schema, install CPU dependencies, establish private data handling | Source audit and pinned environment |
| 10–25 | Group source templates; add private multilingual seeds and legitimate controls; train A | Dataset/split manifests, usable TF-IDF bundle |
| 25–40 | Download E5 with a ten-minute cap, compare frozen encoder + linear head; monitoring and response | Development comparison and working persisted queue |
| 40–50 | Test leakage, duplicate recurrence, persistence, export parity and HTTP contract; freeze | Verified bundle and configuration |
| 50–60 | Once-only final evaluation, replay, private ZIP and handoff | Scorecard, README, notebooks, limitations |

The work may finish earlier. Do not spend spare time tuning on final results.

## Budget decisions

- Candidate A: character TF-IDF `(3,5)` and balanced logistic regression, C=0.5/2.0.
- Candidate B: frozen `intfloat/multilingual-e5-small` and the same head grid,
  only if CPU setup/download fits. Pin resolved revision; use `query: ` prefix,
  normalization and a 256-token cap. No encoder fine-tuning.
- Selection uses `val_select`. Prefer B when within 0.02 macro-F1 of A, subject
  to measured runtime. Thresholds use `val_cal`; final data never tune them.
- If A wins, use its lexical reference bank in this one-hour fallback. This is
  an explicit departure from the original two-component semantic monitor and
  reduces multilingual/semantic capability. Report the representation used.
- Use an explicit 20-report demo window with stride 5 and two elevated windows.
  Calibrate its threshold using group-resampled normal development traffic.
- Use every prediction for novelty, including low classifier scores. Candidate
  clusters require three distinct texts and mean novelty above the cutoff.
- Keep analyst actions durable; do not learn from model predictions. The
  controlled-update experiment is deferred without independently approved
  support examples. Preserve its separate partitions for later work.
- Skip compression, GPU training, cloud hosting and a new dashboard. Supply a
  local API and CLI usable by the application team.

## Current data decision

`final_dataset_output.csv` was supplied locally during this task. It has 33,869
rows, mostly English, with scam categories but no legitimate class. Its source,
licence and privacy review could not be supplied. The user requested proceeding.
Only a capped, conservatively masked sample of four explicit scam categories is
used for a **private unreviewed demonstration**. Ambiguous `spam`, `others` and
`wrong number` categories are excluded. Original CSV is unchanged and ignored.
Masking is not a privacy audit or licence clearance; competition compliance is
unresolved. Do not publish this dataset or its learned artifacts by default.

AI-written English, Sinhala, Tamil, Singlish and Tanglish seeds supply both scam
and legitimate examples. Their generation method and unreviewed status remain
explicit. Translations, notification-prefix variants and opposite-label controls
from one scenario stay in one partition. The repeated prefixes are not new
independent evidence. Private synthetic seed files are excluded from Git.

Report source-specific and language-specific results. A real-scams/synthetic-
controls mixture is vulnerable to source/style shortcuts. Small unreviewed
language slices do not establish supported-language quality. The final remote-
access family is absent from training; development uses a different family.

## Completion criteria

Train a real classifier; export/load it offline; measure held-out results and
normal/shifted monitoring; persist predictions and analyst actions; generate a
private ZIP and reproducible commands. Report failed targets and missed drift
signals as failures. Team review, a controlled update, public-data licensing,
submission and any production readiness remain separate unfinished work.
