| Model | Test macro-F1 [95% group CI] | Macro-F1 on v1 115 rows | Synthetic-only macro-F1 | PR-AUC | Operating precision / recall | Legit high-risk FPR | Review /100 | Normal false-alert windows | Alert delay (reports) | Shifted windows alerting | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v1_shipped | 0.382 [0.28–0.46] | 0.775 | 0.648 | 0.655 | 33.9% / 69.4% | 66.1% | 100 | 11.1% | 20 | 22.2% | 3.8 |
| tfidf_char_raw | 0.904 [0.84–0.98] | 0.746 | 0.681 | 0.969 | 87.2% / 96.5% | 6.9% | 38 | 0.0% | missed | 0.0% | 13.0 |
| tfidf_char | 0.915 [0.86–0.98] | 0.792 | 0.729 | 0.951 | 84.4% / 95.3% | 8.6% | 41 | 0.0% | missed | 0.0% | 12.1 |
| tfidf_union | 0.915 [0.86–0.97] | 0.792 | 0.729 | 0.932 | 81.2% / 96.5% | 10.9% | 41 | 0.0% | missed | 0.0% | 16.9 |
| e5 | 0.913 [0.86–0.98] | 0.765 | 0.713 | 0.953 | 77.3% / 100.0% | 14.4% | 52 | 0.0% | missed | 0.0% | 40.9 |
| **e5_tfidf (selected)** | 0.932 [0.88–0.99] | 0.821 | 0.776 | 0.962 | 83.2% / 98.8% | 9.8% | 40 | 0.0% | missed | 0.0% | 51.9 |
