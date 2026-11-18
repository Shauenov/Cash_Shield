# Negative results (kept on purpose)

## S12 "fresh loan + large cash" combination bonus (+15), tried 18 Nov on the TUNE set
- With S12 at the starting weights: recall 74.4%, but false pauses 2.8% (limit 1%).
- Under the 1% false-pause limit the tuner only reached 61% recall.
- Cause: the honest "spend a fresh loan in cash" scenarios have the same signature as the
  fraud "loan then cash desk" ones, so a combination signal trades recall for false pauses.
- Decision: reverted. The cash-desk-after-loan case stays a known gap and goes in the pitch.
