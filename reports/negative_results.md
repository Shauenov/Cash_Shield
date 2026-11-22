# Negative results (kept on purpose)

## S12 "fresh loan + large cash" combination bonus (+15), tried 18 Nov on the TUNE set
- With S12 at the starting weights: recall 74.4%, but false pauses 2.8% (limit 1%).
- Under the 1% false-pause limit the tuner only reached 61% recall.
- Cause: the honest "spend a fresh loan in cash" scenarios have the same signature as the
  fraud "loan then cash desk" ones, so a combination signal trades recall for false pauses.
- Decision: reverted. The cash-desk-after-loan case stays a known gap and goes in the pitch.

## Desk policy "fresh loan at the cash desk -> teller always asks", tried 22 Nov on the TUNE set
- Idea: close the "cash desk after a loan" gap with a process instead of a signal: at the cash desk,
  an "allow" decision with S1 (loan < 24 h) becomes a teller question. Score unchanged, off by default.
- Result on the tune set: identical scorecard, every metric and every scenario type unchanged.
- Cause: in all 15 tune "loan then cash desk" fraud scenarios the engine already asks the question
  (S1 30 + S3 15 = 45, above the 40 threshold). The gap is not a missing question: 70% of coached
  victims answer "no". A second, identical question from the teller cannot be measured as better.
- Decision: reverted, not shipped. Not measured on the holdout. What a teller could add (seeing the
  phone, a "courier" at the door) is human judgement our synthetic data cannot represent.
