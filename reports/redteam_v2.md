# Red team log

Goal: move >= 2 000 000 KZT out without a pause or hold. The attacker answers 'no' to every question.
Run with `python eval/redteam.py --v2` against `engine/rules.v2.yaml` (`v2-frozen`).

**Honest caveat:** the same person wrote the rules and these attempts, so this is not a blind test. A second person who sees only the screens still has to try.

| # | Attempt | Idea | Money moved before stop | Stopped | Goal reached |
|---|---|---|---:|---|---|
| 1. Straight cash-desk withdrawal | Take almost everything in one go | 0 | op 1 | no |
| 2. Five ATM withdrawals of 500k | Use the ATM limit, answer 'no' to the question | 500 000 | op 2 | no |
| 3. Nine withdrawals of 250k | Stay below the 'large cash' threshold | 1 000 000 | op 5 | no |
| 4. Slow drip, 200k every 45 min | Spread over hours to look ordinary | 1 000 000 | op 6 | no |
| 5. Wait 25 hours, then withdraw | Let the 24-hour 'fresh loan' signal expire | 2 500 000 | never | **YES (bypass)** |
| 6. Transfer to a recipient already known | Make the recipient look familiar | 2 200 000 | never | **YES (bypass)** |
| 7. Transfer to a company (shell firm) | Use the company discount (S9) | 0 | op 1 | no |
| 8. Three transfers to three companies | Split across recipients and shells | 0 | op 1 | no |
| 9. Customer with no loan, normal cash | Plain savings, no loan, no deposit | 500 000 | op 2 (no funds) | no |
| 10. One 400k per day for six days | Stay under every 24-hour window | 2 400 000 | never | **YES (bypass)** |
| 11. Transfer to an old company | Use a firm registered 11 years ago | 2 200 000 | never | **YES (bypass)** |

## Traces (amount: decision(score), -> answer)

- 1. Straight cash-desk withdrawal: `2500k:pause(70)->STOP`
- 2. Five ATM withdrawals of 500k: `500k:ask(50)->no 500k:hold(100)->STOP`
- 3. Nine withdrawals of 250k: `250k:allow(35) 250k:allow(35) 250k:allow(35) 250k:ask(60)->no 250k:hold(90)->STOP`
- 4. Slow drip, 200k every 45 min: `200k:allow(35) 200k:allow(35) 200k:allow(35) 200k:allow(35) 200k:ask(60)->no 200k:hold(90)->STOP`
- 5. Wait 25 hours, then withdraw: `500k:allow(15) 500k:allow(40) 500k:allow(40) 500k:allow(40) 500k:ask(60)->no`
- 6. Transfer to a recipient already known: `2200k:ask(60)->no`
- 7. Transfer to a company (shell firm): `2200k:hold(100)->STOP`
- 8. Three transfers to three companies: `700k:pause(75)->STOP`
- 9. Customer with no loan, normal cash: `500k:allow(35) 500k:insufficient_funds->NO FUNDS, not an engine stop`
- 10. One 400k per day for six days: `400k:ask(50)->no 400k:allow(15) 400k:allow(15) 400k:allow(15) 400k:ask(45)->no 400k:ask(45)->no`
- 11. Transfer to an old company: `2200k:ask(60)->no`

## Result: 4 of 11 attempts reached the goal

- 5. Wait 25 hours, then withdraw: moved 2 500 000 KZT without a stop.
- 6. Transfer to a recipient already known: moved 2 200 000 KZT without a stop.
- 10. One 400k per day for six days: moved 2 400 000 KZT without a stop.
- 11. Transfer to an old company: moved 2 200 000 KZT without a stop.

Findings are not fixed by tuning the weights after the holdout measurement. They go into the README limits and the answers to the jury.
