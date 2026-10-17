# Executed training results

Selected artifact: `svo-38879254a924` — character TF-IDF + logistic regression.

**Status: completed private demonstration; not ready for production or validated multilingual claims.**

All measurements below come from `runs/final/scorecard.json`. Final evaluation was run once after freezing the model. No final scores were used to change it.

| Measurement | Result |
|---|---|
| Held-out messages / independent assigned groups | 115 / 54 |
| Classifier macro-F1 at 0.5 | 0.7748 |
| Classifier scam precision / recall at 0.5 | 90.0% / 84.7% |
| Deployed high-risk precision / recall | 95.2% / 69.4% |
| Legitimate high-risk false positive rate | 10.0% |
| Held-out review workload | 100.0 per 100 messages |
| Normal replay false-alert windows | 11.1% of 9 windows |
| Drift alert delay after onset | 20 reports |
| Fully shifted windows alerting | 22.2% of 9 windows |
| Warm CPU p95 / samples | 1.54 ms / 50 |
| Bundle size | 515,790 bytes |

The 0.90 precision/0.80 recall target passed on development data but **failed recall on held-out data** at the deployed threshold. The ≤5% normal-window false-alert target also failed. Review routing provides no workload reduction in this held-out set. The first temporary candidate cluster signal occurred before shift onset (report 13); no cluster satisfied the candidate rule at replay end. Do not present this as reliable recurring-variant discovery.

## Language slices

| Language | Messages | Assigned groups | Macro-F1 at 0.5 |
|---|---:|---:|---:|
| en | 67 | 54 | 0.6232 |
| si | 12 | 3 | 0.4958 |
| singlish | 12 | 3 | 0.7483 |
| ta | 12 | 3 | 0.3333 |
| tanglish | 12 | 3 | 0.8286 |

All synthetic language examples are unreviewed; non-English slices have only three underlying scenarios. Prefix variants and translations do not add independent evidence. Sinhala and Tamil performance is weak. Imported test messages have only a scam label, while all legitimate controls are synthetic; source/style shortcuts remain a major limitation.

## Verification and omissions

- Five tests passed: split leakage/review gating, Unicode normalization, hash tampering, duplicate recurrence/persistence/idempotency, and HTTP handler validation.
- Extracted ZIP loads successfully; batch/single prediction parity passed for all five language fixtures with zero score difference. Tampering was rejected.
- An explicitly labelled automated response demonstration persisted a rejected queue item. This is not human review and does not approve any retraining data.
- Actual HTTP socket startup could not be tested: the sandbox denies socket creation. The included smoke script can be run outside this sandbox; HTTP request handlers were exercised in memory.
- E5 download hit the ten-minute cap. The resume attempt was rejected by automatic approval review because its service reported a usage limit. Candidate B and semantic monitoring are incomplete; partial files are ignored in `cache/`.
- No encoder fine-tuning, quantization, controlled update, production dashboard, cloud deployment or competition submission was performed.
- Data source/licence and privacy review remain unresolved. Masking is not a privacy audit. Keep data, learned bundles, raw outputs and notebook outputs private.

## Handoff

- Model: `training/runs/final/bundle/`
- Private export: `training/exports/runtime_bundle_svo-38879254a924.zip`
- Scorecard: `training/runs/final/scorecard.json`
- Split/data evidence: `training/runs/final/split_manifest.json`, `training/data/processed/messages.audit.json`
- Final verification: `training/runs/final/verification.json`
- Replay and review log: `training/runs/final/final_replay.sqlite`
- Instructions: [README.md](README.md); revised budget: [PLAN.md](PLAN.md)

No files were staged, committed or pushed.
