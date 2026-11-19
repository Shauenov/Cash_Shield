# Blind red team (facilitator protocol)

**Why:** the first red team (`reports/redteam.md`) was written by the same person who wrote the rules, so it is not blind. This one is done by a second person who has not seen the rules and sees only the screens.

**Rules fixed in advance (plan section 12):** the attacker sees the client screens only, not code and not rules. Goal: get 2 000 000 ₸ out of Gulnar apa without being paused. At least 8 attempts, each written down. Holes that are found are **not** fixed by tuning the weights after the holdout measurement; they go into the README limits and the answers to the jury.

**Time:** about 60 minutes. **People:** you (facilitator) and one tester who is not on the team and has not read the project files.

## 1. Choose the tester

- Someone comfortable with banking apps who enjoys finding loopholes (a developer, a security-minded friend, a student from a fintech course).
- They must not have read the README, `docs/`, `reports/` or the slides. If they have, say so in the notes: the test is then not blind.
- Give them only `docs/blind-red-team-attacker-brief.md` (print it or send that one file).

## 2. Set up

1. Start the stack: `docker compose up --build -d` (the API must be the version with the **Demo: skip time** button; if you built earlier, rebuild).
2. Tester's device: open `http://localhost:8080/#atm` and `#app` only. On a second device, the tester should use the same Wi-Fi: `http://<laptop IP>:8080/#atm`.
3. **Your own window (hidden from the tester):** `http://localhost:8080/#officer` for **Reset demo** and **Demo: skip time +24 h**; `#desk` for cash-desk requests. **The desk and officer screens show scores and reasons, so the tester must not see them.** Tell the tester only the outcome ("paid out" or "not paid out").
4. Click **Reset demo** before every attempt. Make sure the ATM shows Gulnar apa with a balance of 3 000 000 ₸.
5. Open `reports/redteam_blind_data.csv` (or use paper) to note each attempt.

## 3. During the test

- Read the brief aloud, then let the tester start. Do not hint, do not explain a stop, and do not say which signal fired.
- If the tester asks "why did it stop?": "Tell me what you think, and note it." Record their guess.
- Skip time only when they ask for it: click **Demo: skip time +24 h** once per 24 hours they want to wait.
- Cash desk: do it exactly as they say, then report only "paid out" or "not paid out".
- Stop an attempt when: 2 000 000 ₸ or more is out, an operation is paused or held (the ATM and app show a pause screen; at the desk you see a pause), or they give up.
- Aim for at least 8 attempts. If they run dry after 5, ask: "What would you try if you had watched the bank react to 10 victims?"

## 4. What to write down (one row per attempt, `reports/redteam_blind_data.csv`)

| Column | Meaning |
|---|---|
| `attempt` | 1, 2, 3 … |
| `idea` | The tester's plan in their words |
| `channels` | atm, app, desk, or a mix |
| `steps` | What was done: amounts, recipient type, answers to questions, time skips |
| `outcome` | `goal reached`, `stopped at step N`, or `gave up` |
| `moved_kzt` | Money that came out before the stop (a number) |
| `goal` | `Y` if 2 000 000 or more came out without a stop, else `N` |
| `notes` | Their guess why it stopped (or worked), surprises, whether the screen confused them |

## 5. Afterwards

1. Save the CSV, then run `python tasks.py redteam-blind`. It writes `reports/redteam_blind.md` with the attempts, how many reached the goal, the money lost per attempt and any problems with the data (for example fewer than 8 attempts).
2. Only now compare with the scripted red team (`reports/redteam.md`): which tactics did the tester find that the script missed, and the other way round?
3. Add each new hole to the README limits and to the jury answers. Do **not** change weights or thresholds. A fix after the holdout is a new version with a new measurement, not a quiet edit.
4. Thank the tester and tell them what you found.

## 6. What this test cannot tell you

- One tester, one hour: it samples a few tactics, not all of them. A tester who finds nothing proves little.
- The tester is not under time pressure and does not have a real victim's reactions.
- The demo is not the bank's real ATM host, and the tester cannot attack the network or the code.
