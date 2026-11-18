# Scorecard (holdout, n_fraud=60, n_normal=120)

| # | Metric | Actual | Target | Minimum | Result |
|---|---|---|---|---|---|
| 1 | Recall (stopped fraud scenarios) | 78.3% | >= 85% | >= 75% | PASS |
| 2 | Recall without relying on the question | 66.7% | >= 70% | >= 60% | PASS |
| 3 | False interventions (any), normal | 4.2% | <= 5% | <= 10% | PASS |
| 4 | False pauses, normal | 0.0% | <= 1% | <= 3% | PASS |
| 5 | Pause precision | 100.0% | >= 95% | >= 90% | PASS |
| 6 | Money saved | 71.5% | >= 70% | >= 55% | PASS |
| 7 | Recall drop without camera | 1.7 pp | <= 3 pp | <= 5 pp | PASS |
| 8 | Evasion recall (split/headset/video) | 78.6% | >= 85% | >= 75% | PASS |
| 10 | Explainability | 100.0% | 100% | 100% | PASS |
| 11 | Fairness gap (FPR by age group) | 8.3 pp | <= 5 pp | <= 8 pp | FAIL |

Recall 95% Wilson interval: 66% to 87%.
FPR by age group: 18-34 0.0%, 35-54 8.3%, 55+ 3.3%.

## By scenario type

| Type | Label | N | Stopped (with question) | Stopped (pause/hold only) | Any intervention |
|---|---|---:|---:|---:|---:|
| split_below_limit | fraud | 6 | 6 | 4 | 6 |
| small_withdrawal | normal | 36 | 0 | 0 | 0 |
| contractor_new_payee | normal | 12 | 0 | 0 | 0 |
| deposit_close_transfer | fraud | 14 | 14 | 14 | 14 |
| planned_purchase | normal | 12 | 0 | 0 | 1 |
| pensioner_all | normal | 12 | 0 | 0 | 0 |
| loan_then_cash_desk | fraud | 10 | 7 | 6 | 9 |
| headset | fraud | 4 | 2 | 2 | 3 |
| savings_no_loan | fraud | 8 | 1 | 1 | 2 |
| phone_call_at_atm | normal | 4 | 0 | 0 | 0 |
| loan_then_atm_series | fraud | 14 | 14 | 13 | 14 |
| salary_day | normal | 16 | 0 | 0 | 0 |
| known_transfer | normal | 20 | 0 | 0 | 0 |
| loan_honest_spend | normal | 8 | 0 | 0 | 4 |
| video_call | fraud | 4 | 3 | 0 | 3 |

All data is synthetic and invented by the team. These numbers show the mechanism works without overfitting to individual examples; they do not prove an effect on real customers.
