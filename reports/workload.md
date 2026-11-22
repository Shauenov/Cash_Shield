# Officer workload estimate

All data is synthetic and invented by the team. Counts are per operation, replayed with the frozen rules.

| Set | Label | Operations | Question only | Pause or hold (officer) |
|---|---|---:|---:|---:|
| tune | normal | 184 | 6 (3.3%) | 0 (0.0%) |
| tune | fraud | 134 | 40 (29.9%) | 56 (41.8%) |
| holdout | normal | 122 | 5 (4.1%) | 0 (0.0%) |
| holdout | fraud | 85 | 19 (22.4%) | 40 (47.1%) |

Normal operations, both sets: 0 of 306 paused or held. 95% upper bound: 1.0% of such operations.

## Reviews a day from honest customers (illustrative)

Volume = operations a day that look like our scenarios (large cash or transfers). Small everyday payments are not in the scenarios and are assumed never to be paused.

| Such operations a day | Expected (observed rate) | Worst case (95% upper bound) |
|---:|---:|---:|
| 1 000 | 0 | 10 |
| 5 000 | 0 | 49 |
| 20 000 | 0 | 195 |

## What this does not say

- The bank's real volume of large operations is unknown; the volumes above are placeholders.
- The normal scenarios are deliberately hard (5 of 8 types), so real honest operations are probably paused less often, but this is not measured.
- Real fraud cases add to the queue; their number per day is unknown.
- Minutes per review (callback, comment) are not measured.
