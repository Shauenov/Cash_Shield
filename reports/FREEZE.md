# Freeze record (2026-11-18)

- Frozen before any holdout measurement. The holdout was generated (seed 2026) and hashed earlier, and never evaluated.
- Holdout SHA-256: 6cf7a7134c02f3dc54333eedc01342310c4564bacd262f22a1b75fa8f5e99941
- engine/rules.yaml SHA-256 at freeze: 58830c809ffb37ebc79a4db711cf0869e434fdd6da4e640460efb0f5fa3c83ea
- Weights/thresholds chosen by `python tasks.py tune` on the TUNE set only (stage 1 grid + stage 2 coordinate descent).
- Signal S11 (escalation) was added and S12 (loan+cash combo) was tried and reverted, both before the freeze, using the TUNE set only. See negative_results.md.
- Tune-set result at freeze: recall 74.4%, false interventions 3.3%, false pauses 0.0%.
- Rule: after the single holdout measurement, weights, thresholds and scenarios do not change. Only code bugs may be fixed, each logged in the README.
