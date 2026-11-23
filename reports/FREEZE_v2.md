# Freeze: rules v2 (2026-11-23)

Order of events, each a commit:

1. `holdout2-frozen`: v2 scenario sets generated, holdout2 SHA-256 locked in `data/HOLDOUT2.sha256`
   (c20f675e...). No v2 rule existed yet.
2. v2 signals written (S12 loan or deposit money leaves by transfer, S13 drain over 7 days,
   S14 young recipient company; S9 company discount only for companies registered >= 365 days ago).
   Starting weights in `engine/rules.v2.start.yaml`.
3. `python eval/tune.py --v2` on TUNE2 only (339 scenarios): `reports/tuning_v2.md`.
4. `v2-frozen` (this commit): `engine/rules.v2.yaml` = the tuned candidate, version `v2-frozen`.
   Thresholds ask 45, pause 65, hold 85.

Tune2 numbers at the freeze (same set the rules were tuned on, so optimistic):

| | v1 (frozen 18 Nov) | v2 |
|---|---:|---:|
| Recall | 63.6% | 75.2% |
| Recall without relying on the question | 55.0% | 66.7% |
| False interventions, normal | 5.2% | 4.8% |
| False pauses, normal | 0.5% | 1.0% |

Next and only once per version: `python tasks.py eval --set holdout2` (v1) and
`python tasks.py eval --set holdout2 --rules engine/rules.v2.yaml` (v2). Every run is logged in
`reports/holdout2_runs.log`; a second run of the same version is refused.

The same team wrote the rules, the v2 scenario types and both sets. holdout2 protects against
tuning to individual scenarios, not against a shared idea of how scammers behave.
