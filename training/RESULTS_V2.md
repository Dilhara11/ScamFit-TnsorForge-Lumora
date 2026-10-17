# V2 training results: diagnosis, fixes and comparison

Selected: `e5_tfidf` (`svo-e2a46f504b19`). It combines the frozen multilingual-E5 embedding with word and character TF-IDF in one logistic regression (C=256), Platt-calibrated.
Bundle: `runs/v2/candidates/e5_tfidf/bundle/`. Evidence: `runs/v2/development.json`, `runs/v2/comparison.json`.

**Status: classification improved substantially; precision target and drift detection failed on held-out data. Still a private unreviewed demonstration.**

## 1. What went wrong in v1

Ordered by impact. Each finding was measured on the shipped bundle or the data.

| # | Problem | Evidence | Consequence |
|---|---|---|---|
| 1 | **Masking shortcut.** `prepare_data.py` masked only the imported CSV, and every CSV row is a scam. Synthetic rows were never masked. | 94% of CSV rows contain `[NAME_OR_WORD]` and 0 synthetic rows do. **All of the top 30 scam features** in `model.joblib` are pieces of `[NAME_OR_WORD]`. Presidio tags (`<DATE_TIME>`, `<URL>`, `<PHONE_NUMBER>`…) also occur only in scam rows. | The model learned "masked CSV text = scam". Raw text at inference never contains those tokens (train/serve skew). On real legitimate SMS, v1 flags **78%** as high-risk. |
| 2 | **No real legitimate data.** Source = class. | Train has 6 legitimate scenarios (60 rows = 6 × 5 languages × 2 prefix copies). val_select and val_cal have 2 each; test has 3. | Every legitimate metric rested on 2–3 scenario groups. `"The office opens tomorrow."` scores 0.52, i.e. scam. |
| 3 | **Selection and thresholds fitted on tiny partitions.** | C was chosen from 2 values on 2 legitimate groups, and the high-risk threshold was set to the exact score of one `val_cal` row. | The dev target was "met"; held-out recall then dropped to 69%. |
| 4 | **Uncalibrated scores with a fixed 0.2 low-risk cut.** | `class_weight=balanced` shifts the scores, and 0.2 wasn't derived from any data. | Review workload was 100 per 100, so routing did nothing. |
| 5 | **Monitor thresholds fitted in-sample.** | The novelty 95th percentile and the drift threshold both came from the same 88 `val_cal` rows, with whole groups (10 translations) inserted back-to-back. | 11% false alerts in the normal replay and **33% in the benign-only replay**. |
| 6 | **Cluster cut at the grid edge.** | `cluster_similarity = 0.3`, the lowest grid value. | Clusters chain together; a "candidate" fired before the shift (report 13). |
| 7 | Prefix copies counted as independent evidence. | Each synthetic text appears with and without "Notice:". | Synthetic scenarios were double-weighted. |
| 8 | **Windows portability.** | `import resource` crashed `evaluate.py`; `read_text()` without UTF-8 can't read Sinhala/Tamil; `core.autocrlf` + no `.gitattributes` rewrote bundle text files, so **the shipped bundle fails its own hash check**, and the API would refuse to start. | v1 couldn't be reproduced or verified on this machine. |
| 9 | E5 (Candidate B) never ran. | Download hit the 10-minute cap. | No semantic or multilingual representation was compared. |

## 2. What changed, and why

| Fix | Where | Rationale |
|---|---|---|
| One masking pipeline (`canonical`) for every source, at train **and** inference | `src/svo/v2.py` | The CSV can't be unmasked, so all text is degraded the same way and the masks no longer identify the source. |
| +1,000 real legitimate SMS (UCI ham, CC BY 4.0; 993 groups), masked like the CSV | `scripts/add_public_controls.py` | Real legitimate traffic, so source no longer equals label. Spam is not used (spam ≠ fraud). |
| Pooled train+val_select+val_cal; 5-fold × 3 **grouped** CV; vectorizers fitted per fold; refit on the whole pool | `src/svo/train_v2.py` | The plan's small-data fallback, made rigorous. Scenario groups never cross folds. |
| Selection on **source-stratified** macro-F1 | `train_v2.stratified` | Pooled F1 was ~0.95 just from separating chat from CSV. The per-stratum mean can't be won from source style. |
| Source-balanced sample weights; prefix copies share one weight | `v2.duplicate_weights` | Pass 1 had C at the grid edge for every model because the synthetic multilingual rows were ~7% of the loss (archived in `runs/v2_pass1_superseded/`). |
| Platt calibration and both thresholds from out-of-fold scores; low-risk cut = at most 2% of dev scams | `train_v2.export` | Thresholds come from ~1,400 rows instead of one row; the low-risk band is data-driven. |
| Out-of-group novelty; drift threshold from simulated row-by-row normal streams with the real two-window rule; cluster cut ≥ 99th percentile of unrelated pairs | `train_v2.tune_monitor` | Removes the in-sample fitting and the grid-edge cluster cut. |
| E5 downloaded and pinned (`614241f6`), embeddings cached | `cache/` | Candidate B and an early-fusion candidate could finally be compared. |
| UTF-8/LF IO, portable `evaluate.py`, `.gitattributes`, LF-tolerant baseline verification | various | Reproducible and verifiable on Windows. |

## 3. Comparison (held-out, run once, identical rows)

Test = 259 messages / 201 groups (115 v1 rows + 144 new UCI ham). Thresholds are each model's own deployed thresholds.

| Model | Test macro-F1 [95% group CI] | Macro-F1, v1's 115 rows | Synthetic-only macro-F1 | PR-AUC | Operating precision / recall | Legit high-risk FPR | Review /100 | p95 ms | Bundle |
|---|---|---|---|---|---|---|---|---|---|
| v1 shipped | 0.382 [0.28–0.46] | 0.775 | 0.648 | 0.655 | 33.9% / 69.4% | 66.1% | 100 | 3.8 | 0.5 MB |
| tfidf_char_raw (ablation) | 0.904 [0.84–0.98] | 0.746 | 0.681 | 0.969 | 87.2% / 96.5% | 6.9% | 38 | 13 | 1.8 MB |
| tfidf_char | 0.915 [0.86–0.98] | 0.792 | 0.729 | 0.951 | 84.4% / 95.3% | 8.6% | 41 | 12 | 1.7 MB |
| tfidf_union | 0.915 [0.86–0.97] | 0.792 | 0.729 | 0.932 | 81.2% / 96.5% | 10.9% | 41 | 17 | 2.3 MB |
| e5 | 0.913 [0.86–0.98] | 0.765 | 0.713 | 0.953 | 77.3% / 100% | 14.4% | 52 | 41 | 473 MB |
| **e5_tfidf (selected)** | **0.932 [0.88–0.99]** | **0.821** | **0.776** | 0.962 | 83.2% / **98.8%** | 9.8% | 40 | 52 | 477 MB |

Language macro-F1 at 0.5 for the selected model: en 0.955, si 0.829, singlish 0.829, ta 1.000, tanglish 0.625. Non-English slices have only 3 scenarios each.

How to read it:
- The selected model was chosen on development data **before** this table existed (`freeze.json`). The `e5_tfidf` choice follows the plan's rule: within 0.02 of the best lexical model, and the encoder also supplies semantic monitoring.
- On v1's own 115 rows, v1 reproduces its published 0.775, which checks the comparison. v2 reaches 0.821. Those rows were already exposed by the v1 report, so treat that column as comparable but not untouched.
- The ablation (`tfidf_char_raw`, no shared masking) scores highest in development (0.937) and lowest on v1's rows (0.746). That gap is the shortcut showing itself, which is why it was excluded from selection.
- The confidence intervals overlap for all v2 models. The ranking among them is not statistically established.

## 4. Failed targets and limits

- **Precision ≥ 0.90 failed on held-out data (83.2%)**; it passed in development (0.905). 15 of the 17 false positives are synthetic formal notices, from one or two of only **3** synthetic legitimate test scenarios. Real UCI ham has a 1.4% false-positive rate. Formal legitimate bank/delivery notices exist only as 10 synthetic development scenarios. This is the main remaining gap, and it needs data, not modelling.
- **Drift detection failed for every v2 model**: no alert, 0% of shifted windows. The unseen remote-access scams *are* caught (100% high-risk, 100% routed to review), but none is "novel". The novelty 95th percentile is set by UCI chat, which is naturally all-unique, while synthetic messages always have close neighbours. v1's alert was partly noise (33% false alerts on benign-only traffic). The candidate-cluster rule also produced no candidates.
- Proposed monitor fix, not applied because it would turn `shift_demo` into development data: per-source novelty thresholds plus leave-one-family-out simulation on development scam families. After that, `shift_demo` must be replaced by a new locked replay.
- Real legitimate data are informal chat; data licence/privacy for the CSV is unresolved; nothing is human-reviewed; the scores are calibrated under a balanced prior, not deployment prevalence.

## 5. Next steps, by expected gain

1. Write or collect 50+ **formal legitimate** scenarios (OTP warnings, delivery updates, bank notices) in all five languages. This is the fix for the precision miss.
2. Re-prepare from the raw CSV with **light masking** (real PII only, not every capitalised word) applied to all sources. The 22k English rows allow far more than 400 scams.
3. Apply the monitor fix above and build a new locked shift replay.
4. Encoder fine-tuning (Candidate C) only after 1–3. The fusion head already captures most of what E5 adds.

## 6. Handoff notes for the application

The API engine now serves this bundle; see [VERIFICATION.md](../app/server/VERIFICATION.md) for what was verified and what still needs a Docker host. If a small image matters more, `tfidf_char` is the lexical fallback: 1.7 MB, 12 ms, macro-F1 0.915. Switching only needs `SVO_MODEL_DIR` and `SVO_EXPECTED_MODEL_VERSION=svo-b3ab151e73a2`, plus that bundle in the Docker context.

Post-freeze edits, none of which change a frozen bundle: `evaluate_v2.py` gained the LF-tolerant v1 baseline loader (before the evaluation that produced the results), and `train_v2.py` now leaves the hub's `.cache/` metadata out of future bundles. Both files' recorded source hashes therefore differ from the current files; the engine checks only runtime modules.

The bundled encoder directories are git-ignored (each holds ~450 MB of weights; GitHub's limit is 100 MB). Re-create them with `scripts/download_encoder.py` at the pinned revision. The existing CRLF working copy of `runs/final/bundle` needs a fresh checkout to pass `verify_bundle` again; `.gitattributes` prevents it from recurring. No files were staged, committed or pushed.
