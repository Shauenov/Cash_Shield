# Tuning report (TUNE set only, 180 normal + 90 fraud)

Candidates evaluated: 324. Feasible (FPR<=5%, false pause<=1%): 171. feasible set found.

## Top 10 candidates

| ask | pause | dS1 | dS4 | dS7 | recall | recall no-question | FPR any | FPR pause |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 40 | 55 | -5 | +5 | +5 | 73.3% | 61.1% | 3.3% | 0.0% |
| 40 | 55 | +0 | +5 | +5 | 73.3% | 61.1% | 3.3% | 0.0% |
| 40 | 55 | -5 | -5 | +5 | 72.2% | 60.0% | 3.3% | 0.0% |
| 40 | 55 | -5 | +0 | +5 | 72.2% | 60.0% | 3.3% | 0.0% |
| 40 | 55 | +0 | -5 | +5 | 72.2% | 60.0% | 3.3% | 0.0% |
| 40 | 55 | +0 | +0 | +5 | 72.2% | 60.0% | 3.3% | 0.0% |
| 45 | 55 | +0 | +0 | +5 | 72.2% | 60.0% | 3.3% | 0.0% |
| 45 | 55 | +0 | +5 | +5 | 72.2% | 61.1% | 3.3% | 0.0% |
| 45 | 55 | -5 | +0 | +5 | 71.1% | 62.2% | 3.3% | 0.0% |
| 45 | 55 | -5 | +5 | +5 | 71.1% | 64.4% | 3.3% | 0.0% |

## Stage 2: coordinate descent (tune set only)

- w:S4+5 -> recall 74.4%, FPR 3.3%

## Chosen: ask=40, pause=55, weights={'S1': 30, 'S2': 20, 'S3': 15, 'S4': 30, 'S5': 15, 'S6': 20, 'S7': 20, 'S8': 40, 'S9': -15, 'S10': 10, 'S11': 20}
recall 74.4%, recall without question 62.2%, FPR any 3.3%, FPR pause 0.0%

Overfitting warning: 270 scenarios written by the same team, 12 free parameters. Only the single holdout measurement says whether this generalizes.
