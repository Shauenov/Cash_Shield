# Scorecard (tune, n_fraud=90, n_normal=180)

| # | Metric | Actual | Target | Minimum | Result |
|---|---|---|---|---|---|
| 1 | Recall (stopped fraud scenarios) | 74.4% | >= 85% | >= 75% | FAIL |
| 2 | Recall without relying on the question | 62.2% | >= 70% | >= 60% | PASS |
| 3 | False interventions (any), normal | 3.3% | <= 5% | <= 10% | PASS |
| 4 | False pauses, normal | 0.0% | <= 1% | <= 3% | PASS |
| 5 | Pause precision | 100.0% | >= 95% | >= 90% | PASS |
| 6 | Money saved | 65.2% | >= 70% | >= 55% | PASS |
| 7 | Recall drop without camera | 4.4 pp | <= 3 pp | <= 5 pp | PASS |
| 8 | Evasion recall (split/headset/video) | 76.2% | >= 85% | >= 75% | PASS |
| 10 | Explainability | 100.0% | 100% | 100% | PASS |
| 11 | Fairness gap (FPR by age group) | 5.6 pp | <= 5 pp | <= 8 pp | PASS |

Recall 95% Wilson interval: 65% to 82%.
FPR by age group: 18-34 6.7%, 35-54 5.1%, 55+ 1.1%.

## By scenario type

| Type | Label | N | Stopped (with question) | Stopped (pause/hold only) | Any intervention |
|---|---|---:|---:|---:|---:|
| salary_day | normal | 24 | 0 | 0 | 0 |
| small_withdrawal | normal | 54 | 0 | 0 | 0 |
| known_transfer | normal | 30 | 0 | 0 | 0 |
| loan_honest_spend | normal | 12 | 0 | 0 | 5 |
| contractor_new_payee | normal | 18 | 0 | 0 | 0 |
| loan_then_atm_series | fraud | 21 | 20 | 17 | 21 |
| loan_then_cash_desk | fraud | 15 | 4 | 3 | 15 |
| deposit_close_transfer | fraud | 21 | 21 | 21 | 21 |
| planned_purchase | normal | 18 | 0 | 0 | 0 |
| headset | fraud | 6 | 4 | 2 | 4 |
| video_call | fraud | 6 | 3 | 3 | 5 |
| phone_call_at_atm | normal | 6 | 0 | 0 | 1 |
| savings_no_loan | fraud | 12 | 6 | 4 | 7 |
| pensioner_all | normal | 18 | 0 | 0 | 0 |
| split_below_limit | fraud | 9 | 9 | 6 | 9 |

All data is synthetic and invented by the team. These numbers show the mechanism works without overfitting to individual examples; they do not prove an effect on real customers.
