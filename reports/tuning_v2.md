# Tuning report (TUNE2 set only, 210 normal + 129 fraud)

Candidates evaluated: 324. Feasible (FPR<=5%, false pause<=1%): 24. feasible set found.

## Top 10 candidates

| ask | pause | dS1 | dS4 | dS7 | recall | recall no-question | FPR any | FPR pause |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 45 | 65 | +5 | -5 | -5 | 71.3% | 63.6% | 4.3% | 1.0% |
| 45 | 65 | +5 | -5 | +0 | 71.3% | 63.6% | 4.3% | 1.0% |
| 45 | 65 | +5 | -5 | +5 | 71.3% | 63.6% | 4.3% | 1.0% |
| 45 | 65 | +0 | -5 | -5 | 68.2% | 61.2% | 4.3% | 1.0% |
| 45 | 65 | +0 | -5 | +0 | 68.2% | 61.2% | 4.3% | 1.0% |
| 45 | 65 | +0 | -5 | +5 | 68.2% | 61.2% | 4.3% | 1.0% |
| 45 | 70 | +5 | -5 | -5 | 67.4% | 59.7% | 4.3% | 0.5% |
| 45 | 70 | +5 | -5 | +0 | 67.4% | 59.7% | 4.3% | 0.5% |
| 45 | 70 | +5 | -5 | +5 | 67.4% | 59.7% | 4.3% | 0.5% |
| 45 | 65 | -5 | -5 | -5 | 63.6% | 57.4% | 1.9% | 1.0% |

## Stage 2: coordinate descent (tune set only)

- w:S11+5 -> recall 72.1%, FPR 4.3%
- w:S13+5 -> recall 72.9%, FPR 4.8%
- w:S11+5 -> recall 75.2%, FPR 4.8%

## Chosen: ask=45, pause=65, weights={'S1': 35, 'S2': 20, 'S3': 15, 'S4': 25, 'S5': 15, 'S6': 20, 'S7': 15, 'S8': 40, 'S9': -15, 'S10': 10, 'S11': 30, 'S12': 25, 'S13': 30, 'S14': 25}
recall 75.2%, recall without question 66.7%, FPR any 4.8%, FPR pause 1.0%

Overfitting warning: 339 scenarios written by the same team, 14 free parameters. Only the single holdout measurement says whether this generalizes.
