# Red team log

Goal: move >= 2 000 000 KZT out without a pause or hold. The attacker answers 'no' to every question.
Run with `python eval/redteam.py` against the frozen rules (`thresholds-frozen`).

**Honest caveat:** the same person wrote the rules and these attempts, so this is not a blind test. A second person who sees only the screens still has to try.

| # | Attempt | Idea | Money moved before stop | Stopped | Goal reached |
|---|---|---|---:|---|---|
| 1. Straight cash-desk withdrawal | Take almost everything in one go | 0 | op 1 | no |
| 2. Five ATM withdrawals of 500k | Use the ATM limit, answer 'no' to the question | 500 000 | op 2 | no |
| 3. Nine withdrawals of 250k | Stay below the 'large cash' threshold | 750 000 | op 4 | no |
| 4. Slow drip, 200k every 45 min | Spread over hours to look ordinary | 800 000 | op 5 | no |
| 5. Wait 25 hours, then withdraw | Let the 24-hour 'fresh loan' signal expire | 1 000 000 | op 3 | no |
| 6. Transfer to a recipient already known | Make the recipient look familiar | 2 200 000 | never | **YES (bypass)** |
| 7. Transfer to a company (shell firm) | Use the company discount (S9) | 2 200 000 | never | **YES (bypass)** |
| 8. Three transfers to three companies | Split across recipients and shells | 2 100 000 | never | **YES (bypass)** |
| 9. Customer with no loan, normal cash | Plain savings, no loan, no deposit | 500 000 | op 2 | no |
| 10. One 400k per day for six days | Stay under every 24-hour window | 2 400 000 | never | **YES (bypass)** |

## Traces (amount: decision(score), -> answer)

- 1. Straight cash-desk withdrawal: `2500k:pause(65)->STOP`
- 2. Five ATM withdrawals of 500k: `500k:ask(45)->no 500k:hold(95)->STOP`
- 3. Nine withdrawals of 250k: `250k:allow(30) 250k:allow(30) 250k:allow(30) 250k:pause(60)->STOP`
- 4. Slow drip, 200k every 45 min: `200k:allow(30) 200k:allow(30) 200k:allow(30) 200k:allow(30) 200k:pause(60)->STOP`
- 5. Wait 25 hours, then withdraw: `500k:allow(15) 500k:ask(45)->no 500k:pause(65)->STOP`
- 6. Transfer to a recipient already known: `2200k:allow(30)`
- 7. Transfer to a company (shell firm): `2200k:allow(30)`
- 8. Three transfers to three companies: `700k:allow(30) 700k:allow(30) 700k:allow(30)`
- 9. Customer with no loan, normal cash: `500k:allow(35) 500k:pause(65)->STOP`
- 10. One 400k per day for six days: `400k:ask(45)->no 400k:allow(15) 400k:allow(15) 400k:allow(15) 400k:allow(15) 400k:allow(15)`

## Result: 4 of 10 attempts reached the goal

- 6. Transfer to a recipient already known: moved 2 200 000 KZT without a stop.
- 7. Transfer to a company (shell firm): moved 2 200 000 KZT without a stop.
- 8. Three transfers to three companies: moved 2 100 000 KZT without a stop.
- 10. One 400k per day for six days: moved 2 400 000 KZT without a stop.

Findings are not fixed by tuning the weights after the holdout measurement. They go into the README limits and the answers to the jury.
