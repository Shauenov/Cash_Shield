# Scorecard (tune2, n_fraud=129, n_normal=210)

| # | Metric | Actual | Target | Minimum | Result |
|---|---|---|---|---|---|
| 1 | Recall (stopped fraud scenarios) | 75.2% | >= 85% | >= 75% | PASS |
| 2 | Recall without relying on the question | 66.7% | >= 70% | >= 60% | PASS |
| 3 | False interventions (any), normal | 4.8% | <= 5% | <= 10% | PASS |
| 4 | False pauses, normal | 1.0% | <= 1% | <= 3% | PASS |
| 5 | Pause precision | 97.7% | >= 95% | >= 90% | PASS |
| 6 | Money saved | 68.4% | >= 70% | >= 55% | PASS |
| 7 | Recall drop without camera | 2.3 pp | <= 3 pp | <= 5 pp | PASS |
| 8 | Evasion recall (split/headset/video) | 81.8% | >= 85% | >= 75% | PASS |
| 10 | Explainability | 100.0% | 100% | 100% | PASS |
| 11 | Fairness gap (FPR by age group) | 3.1 pp | <= 5 pp | <= 8 pp | PASS |

Recall 95% Wilson interval: 67% to 82%.
FPR by age group: 18-34 7.0%, 35-54 4.8%, 55+ 3.8%.

## By scenario type

| Type | Label | N | Stopped (with question) | Stopped (pause/hold only) | Any intervention |
|---|---|---:|---:|---:|---:|
| loan_then_atm_series | fraud | 21 | 20 | 16 | 21 |
| contractor_new_payee | normal | 18 | 0 | 0 | 0 |
| loan_transfer_company | fraud | 15 | 14 | 14 | 14 |
| salary_day | normal | 24 | 0 | 0 | 0 |
| loan_then_cash_desk | fraud | 15 | 11 | 10 | 15 |
| small_withdrawal | normal | 54 | 0 | 0 | 0 |
| deposit_close_transfer | fraud | 21 | 19 | 19 | 21 |
| split_below_limit | fraud | 9 | 9 | 8 | 9 |
| known_transfer | normal | 30 | 0 | 0 | 0 |
| slow_drip_days | fraud | 12 | 7 | 5 | 10 |
| headset | fraud | 6 | 6 | 5 | 6 |
| phone_call_at_atm | normal | 6 | 0 | 0 | 0 |
| savings_no_loan | fraud | 12 | 1 | 1 | 2 |
| video_call | fraud | 6 | 5 | 4 | 5 |
| family_large_transfer | normal | 12 | 0 | 0 | 0 |
| planned_purchase | normal | 18 | 0 | 0 | 1 |
| pensioner_all | normal | 18 | 0 | 0 | 0 |
| loan_honest_spend | normal | 12 | 1 | 1 | 5 |
| loan_transfer_known | fraud | 12 | 5 | 4 | 10 |
| weekly_spending | normal | 18 | 1 | 1 | 4 |

All data is synthetic and invented by the team. These numbers show the mechanism works without overfitting to individual examples; they do not prove an effect on real customers.
