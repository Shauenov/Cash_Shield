# Scorecard (holdout2, n_fraud=86, n_normal=140)

| # | Metric | Actual | Target | Minimum | Result |
|---|---|---|---|---|---|
| 1 | Recall (stopped fraud scenarios) | 76.7% | >= 85% | >= 75% | PASS |
| 2 | Recall without relying on the question | 59.3% | >= 70% | >= 60% | FAIL |
| 3 | False interventions (any), normal | 4.3% | <= 5% | <= 10% | PASS |
| 4 | False pauses, normal | 2.1% | <= 1% | <= 3% | PASS |
| 5 | Pause precision | 94.4% | >= 95% | >= 90% | PASS |
| 6 | Money saved | 69.0% | >= 70% | >= 55% | PASS |
| 7 | Recall drop without camera | 7.0 pp | <= 3 pp | <= 5 pp | FAIL |
| 8 | Evasion recall (split/headset/video) | 63.6% | >= 85% | >= 75% | FAIL |
| 10 | Explainability | 100.0% | 100% | 100% | PASS |
| 11 | Fairness gap (FPR by age group) | 3.2 pp | <= 5 pp | <= 8 pp | PASS |

Recall 95% Wilson interval: 67% to 84%.
FPR by age group: 18-34 5.7%, 35-54 2.5%, 55+ 4.6%.

## By scenario type

| Type | Label | N | Stopped (with question) | Stopped (pause/hold only) | Any intervention |
|---|---|---:|---:|---:|---:|
| deposit_close_transfer | fraud | 14 | 13 | 13 | 14 |
| pensioner_all | normal | 12 | 0 | 0 | 0 |
| loan_then_atm_series | fraud | 14 | 14 | 10 | 14 |
| loan_transfer_company | fraud | 10 | 10 | 10 | 10 |
| known_transfer | normal | 20 | 0 | 0 | 0 |
| loan_then_cash_desk | fraud | 10 | 8 | 6 | 10 |
| small_withdrawal | normal | 36 | 0 | 0 | 0 |
| salary_day | normal | 16 | 0 | 0 | 0 |
| loan_transfer_known | fraud | 8 | 4 | 0 | 7 |
| family_large_transfer | normal | 8 | 0 | 0 | 0 |
| weekly_spending | normal | 12 | 2 | 2 | 4 |
| loan_honest_spend | normal | 8 | 1 | 1 | 2 |
| headset | fraud | 4 | 4 | 4 | 4 |
| slow_drip_days | fraud | 8 | 2 | 1 | 6 |
| planned_purchase | normal | 12 | 0 | 0 | 0 |
| video_call | fraud | 4 | 2 | 1 | 2 |
| split_below_limit | fraud | 6 | 6 | 4 | 6 |
| savings_no_loan | fraud | 8 | 3 | 2 | 4 |
| contractor_new_payee | normal | 12 | 0 | 0 | 0 |
| phone_call_at_atm | normal | 4 | 0 | 0 | 0 |

All data is synthetic and invented by the team. These numbers show the mechanism works without overfitting to individual examples; they do not prove an effect on real customers.
