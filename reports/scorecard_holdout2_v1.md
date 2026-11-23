# Scorecard (holdout2, n_fraud=86, n_normal=140)

| # | Metric | Actual | Target | Minimum | Result |
|---|---|---|---|---|---|
| 1 | Recall (stopped fraud scenarios) | 67.4% | >= 85% | >= 75% | FAIL |
| 2 | Recall without relying on the question | 57.0% | >= 70% | >= 60% | FAIL |
| 3 | False interventions (any), normal | 3.6% | <= 5% | <= 10% | PASS |
| 4 | False pauses, normal | 1.4% | <= 1% | <= 3% | PASS |
| 5 | Pause precision | 96.1% | >= 95% | >= 90% | PASS |
| 6 | Money saved | 60.8% | >= 70% | >= 55% | PASS |
| 7 | Recall drop without camera | 4.7 pp | <= 3 pp | <= 5 pp | PASS |
| 8 | Evasion recall (split/headset/video) | 63.6% | >= 85% | >= 75% | FAIL |
| 10 | Explainability | 100.0% | 100% | 100% | PASS |
| 11 | Fairness gap (FPR by age group) | 2.1 pp | <= 5 pp | <= 8 pp | PASS |

Recall 95% Wilson interval: 57% to 76%.
FPR by age group: 18-34 2.9%, 35-54 5.0%, 55+ 3.1%.

## By scenario type

| Type | Label | N | Stopped (with question) | Stopped (pause/hold only) | Any intervention |
|---|---|---:|---:|---:|---:|
| deposit_close_transfer | fraud | 14 | 14 | 14 | 14 |
| pensioner_all | normal | 12 | 0 | 0 | 0 |
| loan_then_atm_series | fraud | 14 | 14 | 12 | 14 |
| loan_transfer_company | fraud | 10 | 4 | 2 | 5 |
| known_transfer | normal | 20 | 0 | 0 | 0 |
| loan_then_cash_desk | fraud | 10 | 8 | 6 | 10 |
| small_withdrawal | normal | 36 | 0 | 0 | 0 |
| salary_day | normal | 16 | 0 | 0 | 0 |
| loan_transfer_known | fraud | 8 | 0 | 0 | 0 |
| family_large_transfer | normal | 8 | 0 | 0 | 0 |
| weekly_spending | normal | 12 | 1 | 1 | 4 |
| loan_honest_spend | normal | 8 | 1 | 1 | 1 |
| headset | fraud | 4 | 4 | 4 | 4 |
| slow_drip_days | fraud | 8 | 2 | 2 | 4 |
| planned_purchase | normal | 12 | 0 | 0 | 0 |
| video_call | fraud | 4 | 2 | 1 | 2 |
| split_below_limit | fraud | 6 | 6 | 4 | 6 |
| savings_no_loan | fraud | 8 | 4 | 4 | 4 |
| contractor_new_payee | normal | 12 | 0 | 0 | 0 |
| phone_call_at_atm | normal | 4 | 0 | 0 | 0 |

All data is synthetic and invented by the team. These numbers show the mechanism works without overfitting to individual examples; they do not prove an effect on real customers.
