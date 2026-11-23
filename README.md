# Cash Shield (Sabyr)

Entry for the V ITU Hackathon-2026 (Bank CenterCredit case "Innovations and cybersecurity in banking").

**All data is synthetic and invented by the team.** The numbers show that the mechanism works without overfitting to individual examples. They do not show what would happen with real customers.

## 1. The problem

A scammer on the phone talks a customer into taking a loan, withdrawing cash or moving money to a "safe account". The customer does it personally, so the bank sees ordinary operations. Digital antifraud watches transfers, not the person at the ATM or the cash desk.

## 2. What it does

One risk engine on bank signals serves three channels: ATM, cash desk and mobile app.

![components](docs/architecture.png)

| Score | Decision | What the customer sees |
|---|---|---|
| 0-39 | allow | nothing |
| 40-54 | ask | one question: "Is someone asking you by phone to withdraw or transfer this money?" |
| 55-84 | pause | pause screen (30 min), bank callback through the app, teller prompt at the desk |
| 85+ | hold | held until a bank officer decides |

- A trusted person gets a message only if the customer agreed beforehand. The message has no amount and no details.
- The answer "yes" always pauses. A coached victim learns to answer "no", so pausing does not depend only on the answer (see metric 2).
- The camera (phone at the ear) is an optional signal worth +10 points. Without it, recall drops by 1.7 points.
- Age is **not** a signal.
- Only the bank's authorization host can stop a withdrawal. In this demo the host is mocked (`/mock-host/authorize`).
- If the engine does not answer within 500 ms the host approves and logs it (fail-open: a fault in our service never blocks cash).

Signals (weights tuned on the tuning set, then frozen):

| Code | Signal | Weight |
|---|---|---:|
| S1 | Loan issued < 24 h ago | 30 |
| S2 | >= 80% of the balance moved out within 24 h | 20 |
| S3 | Cash >= 300 000 and >= 5x the customer's median | 15 |
| S4 | 2+ withdrawals in 24 h totalling >= 1 000 000 | 30 |
| S5 | Transfer >= 200 000 to a new recipient | 15 |
| S6 | Deposit closed early < 24 h ago | 20 |
| S7 | S5 and S6 together | 20 |
| S8 | Customer pressed "Scammer on the line" < 24 h ago | 40 |
| S9 | Recipient is a company | -15 |
| S10 | Camera: phone at the ear > 3 s (optional) | 10 |
| S11 | Escalation: customer answered "no", then tries again | 20 |

Every non-allow decision returns its reasons (`text_en`, `text_ru`), and a test enforces that.

## 3. Run it

Requires Docker.

```bash
cp .env.example .env
docker compose up --build
```

Then open <http://localhost:8080>:

| Screen | Address |
|---|---|
| ATM | `http://localhost:8080/#atm` |
| Cash desk | `http://localhost:8080/#desk` |
| Mobile app | `http://localhost:8080/#app` |
| Officer console | `http://localhost:8080/#officer` |

Without Docker (Windows, Python 3.11, Node 22):

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn services.api.main:app --port 8000
cd web && npm install && npm run dev      # http://localhost:5173
```

`make` is not used because the team develops on Windows. `python tasks.py <task>` replaces it:

| Command | What it does |
|---|---|
| `python tasks.py data` | Regenerate the scenario sets (fixed seeds, byte-identical) |
| `python tasks.py test` | Engine unit tests with coverage |
| `python tasks.py test-integration` | API endpoint tests |
| `python tasks.py eval` | **Metrics on the frozen holdout** (hash-checked); writes `reports/scorecard.md` |
| `python tasks.py eval --set tune` | Same on the tuning set |
| `python tasks.py tune` | Grid and coordinate search on the tuning set only |
| `python tasks.py workload` | Officer workload estimate: pauses and holds per operation on both sets, 95% upper bound, reviews a day for placeholder volumes; writes `reports/workload.md` |
| `python tasks.py bench` | 1000 authorize calls, latency |
| `python tasks.py demo-check` | Automated API-level rehearsal of the demo (10 runs) |
| `python tasks.py redteam` | Scripted red team, writes `reports/redteam.md` |
| `python tasks.py redteam-blind` | Summarizes the blind red team from `reports/redteam_blind_data.csv` (protocol: `docs/blind-red-team.md`) |
| `python tasks.py usability` | Scores the pause-screen usability test from `reports/usability_data.csv` (protocol: `docs/usability-test.md`) |

Demo customers: Gulnar apa (loan 3 h ago), Marat (control), Aigerim (deposit closed 1 h ago), Serik (buying a car), Bolat (cash desk), Dana. The **Reset demo** button in the officer console restores them.

Demo: the 3-minute script is in `docs/demo-script.md`. A silent, captioned backup walkthrough built from real screenshots of the running app is `pitch/demo-backup.mp4` (about 70 seconds; rebuild with `python pitch/make_video.py`). It is a walkthrough, not a screen recording with narration.

## 4. Metrics (holdout, measured once)

Holdout: 60 fraud and 120 normal synthetic scenarios, SHA-256 `6cf7a7134c02f3dc54333eedc01342310c4564bacd262f22a1b75fa8f5e99941`.
Thresholds were frozen (tag `thresholds-frozen`) before the measurement; see `reports/FREEZE.md`. Every holdout run is logged in `reports/holdout_runs.log`. Re-running `python tasks.py eval` reproduces the numbers.

| # | Metric | Actual | Target | Minimum | vs minimum |
|---|---|---|---|---|---|
| 1 | Recall (fraud scenarios stopped) | 78.3% (95% interval 66-87%) | >= 85% | >= 75% | PASS, target missed |
| 2 | Recall without relying on the question | 66.7% | >= 70% | >= 60% | PASS, target missed |
| 3 | False interventions on normal scenarios | 4.2% | <= 5% | <= 10% | PASS |
| 4 | False pauses | 0.0% | <= 1% | <= 3% | PASS |
| 5 | Pause precision | 100% (on a 33% fraud sample; real precision would be lower) | >= 95% | >= 90% | PASS |
| 6 | Money saved | 71.5% | >= 70% | >= 55% | PASS |
| 7 | Recall drop without camera | 1.7 pp | <= 3 pp | <= 5 pp | PASS |
| 8 | Evasion recall (split, headset, video) | 78.6% (14 scenarios) | >= 85% | >= 75% | PASS, target missed |
| 9 | Latency p95 (1000 calls; about 10 ms in-process on the host, 57 ms inside the Docker container) | 57 ms worst case | <= 300 ms | <= 500 ms | PASS |
| 10 | Explainability | 100% | 100% | 100% | PASS |
| 11 | Fairness gap by age group | 8.3 pp | <= 5 pp | <= 8 pp | **FAIL** |

Not measured: camera accuracy (no camera model in this build), demo reliability, usability, red team. Do not read them as passed.

On fairness: the engine does not use age. The 5 false interventions were 3 among 36 normal scenarios aged 35-54, 2 among 61 aged 55+, and 0 among 23 aged 18-34. With groups this small, one scenario moves a group by 3-4 points, so the gap may be noise, but it is not proven to be. It is reported as a FAIL.

## 5. Data

Everything is generated by `data/generate.py`; the distributions are invented by the team.

- Tune: seed 42, 270 scenarios (180 normal, 90 fraud). Holdout: seed 2026, 180 scenarios (120 normal, 60 fraud), with amounts shifted by +-30% and time gaps by +-50%.
- 8 normal types (5 deliberately hard, for example a pensioner withdrawing everything or an honest customer spending a fresh loan) and 7 fraud types (including split withdrawals, headset and video-call coaching).
- Assumptions: 70% of fraud victims lie to the question; 15% of fraud scenarios include a prior "Scammer on the line" report.
- The same author wrote the rules and both sets. The holdout protects against tuning to individual examples, not against a shared mental model of how scammers behave.

## 6. Known limits

- **A single large cash-desk withdrawal after a loan** is caught only when the victim answers honestly or the amount is a large share of the balance. A combination signal for this (S12) made things worse and was reverted, because honest "spend a fresh loan" customers look the same. See `reports/negative_results.md`.
- **Red team (scripted, not blind; `reports/redteam.md`; a blind round is prepared in `docs/blind-red-team.md` and not yet run): 4 of 10 attempts moved 2 million or more without a stop.** All four were transfers or slow drips: a 2.2M transfer to an already-known recipient, a 2.2M transfer to a company (the company discount cancels the new-recipient signal), three 700k transfers to three companies, and one 400k withdrawal per day for six days. The five cash attempts on Gulnar (attempts 1-5) were all stopped, but four of them lost 500 000 to 1 000 000 before the stop (the one that waited 25 hours lost 1 000 000). Attempt 9 (Dana, 600 000 balance, two withdrawals of 500 000) could never reach the goal: before the balance check was added it counted as an engine stop, now the host refuses the second withdrawal for lack of money and the report says so. These were not fixed by tuning after the measurement.
- **Own savings, no loan** is the weakest type (1 of 8 stopped).
- Video-call coaching is stopped only through the question (3 of 4), never by pause alone.
- Metrics come from synthetic scenarios of one team. They do not say how much a real bank would save.
- No legal point is confirmed by a lawyer: holding a customer's own money for 30 minutes, notifying a third party, using a camera. The pause length is configurable (`PAUSE_MINUTES`, including 0).
- Kazakh and Russian texts (KZ and RU buttons) were written by the team and need a native-speaker review. The screens are English, Kazakh and Russian; the officer console and risk reasons are English (reasons also carry a Russian copy).
- Telegram is simulated unless `TELEGRAM_BOT_TOKEN` and a chat ID are set; the real bot is untested.
- There is no phone-at-ear camera in this build. The ATM screen has a switch that simulates the signal.
- Officer login is a header (`X-Officer-Id`) in the demo, not real authentication.
- The service token is shared by the whole terminal network (the proxy adds it). It proves a call came through the bank's channel, not which customer or officer made it.
- `DEMO_MODE=1` (set in `.env.example`) turns on reset, time skip and the engine-outage switch. Anyone who can open the screens can use them, so run the demo build only on the demo laptop.

## 7. Where a real bank plugs in

| Bank system | What we need | How the demo imitates it |
|---|---|---|
| ATM and card authorization host | Call the engine before answering; support a "hold" status | `/mock-host/authorize` |
| Core banking | Balance, loan and deposit events, transaction history | SQLite tables, seeded customers |
| Mobile app | Show the question and the pause screen; consent settings | The "Mobile app" screen |
| Teller workstation | Show the prompt while issuing cash | The "Cash desk" screen |
| Contact centre | Callback to the customer | A note on the pause screen |
| National Bank Antifraud Centre | Flag for a recipient in the scammer database | Not used as a signal in the MVP |

## 8. Roadmap and the ask

We cannot test on live ATMs after a hackathon and do not ask for it. Realistic steps:

1. **History check (about 4 weeks):** run the engine over de-identified confirmed cases and normal operations in a secure bank environment. Customers see nothing. Success: recall and false-alarm rate on real data, against a threshold the bank sets.
2. **Shadow mode (6-8 weeks):** live operations of one channel, decisions only logged. Success: how many later-confirmed cases the engine flagged early, and how many pauses a day officers would have to review.

Questions and pauses reach real customers only after both. The timelines are our estimates; the bank will name its own. The ask for the hackathon is a test environment and a few hours with the bank's antifraud team.

Not in this build: the camera signal as a real detector, Qaqpan (a button plus a wave radar), Kepil (staged-payment escrow).

## 9. Repository map

```
engine/       risk engine (signals.py, scoring.py, rules.yaml frozen, rules.start.yaml pinned for unit tests)
services/api  FastAPI routes (main.py) over the decision lifecycle (lifecycle.py), ledger adapters (ledger.py: SQLite, in-memory) and the clock (clock.py)
web/          React screens: ATM, cash desk, app, officer console
data/         generator and the two scenario sets (holdout hash in HOLDOUT.sha256)
eval/         evaluate.py (replays scenarios through the same lifecycle), tune.py, bench.py, test_metrics_parity.py
reports/      scorecard.md, tuning.md, FREEZE.md, negative_results.md, holdout_runs.log
docs/         api.md, architecture image
```

## 10. Changes after the freeze

Packaging and evidence only (`.gitattributes` forcing LF line endings, found by the clean-clone check in `reports/clean_machine_check.md`; Docker files, README, `bench.py`, `test-integration` task, `redteam.py` and its log, `demo_check.py`, demo script and backup video, the blind red team protocol and a demo-only "skip time" endpoint (`POST /v1/demo-time-skip`) with a button in the officer console; since 2026-11-21 it moves the API clock forward and does not touch stored data or the engine). No change to weights, thresholds, scenarios or engine code. Any bug fix after the single holdout measurement must be listed here with its reason.

### Bug fixes after the audit (2026-11-19)

All in the API and the screens (`services/api/main.py`, `web/`). The engine, weights, thresholds and scenario sets are unchanged, so the holdout metrics are unchanged (`evaluate.py` calls the engine directly). Each fix has a test in `services/api/test_api.py`.

| # | Bug | Fix |
|---|---|---|
| 1 | No balance check: 50 000 000 withdrawn from an 800 000 account was approved and the balance went negative | The host declines with `decision: insufficient_funds`, nothing moves, event `insufficient_funds`. Release and answer "no" recheck the balance (409) |
| 2 | Anyone could call `demo-engine-down` and switch every decision to fail-open approve | Demo endpoints exist only with `DEMO_MODE=1` (otherwise 404) and need the service token |
| 3 | The 30-minute pause never ended: `pause_until` was stored but not used | A pause past `pause_until` becomes `expired`: the operation is cancelled, nothing moves, event `pause_expired`, the screen says so. A new attempt is scored again. A hold still waits for an officer. Time skip now moves decision times too |
| 4 | The caller could set the operation time and backdate past the 24 h windows (Gulnar 2.5M: pause 65 became allow 35) | The host stamps the time; a `timestamp` is always rejected (422). Since 2026-11-21 the red team replays days with a manual clock instead (see below) |
| 5 | The same `operation_id` sent twice was executed twice | `/mock-host/authorize` is idempotent by `operation_id` (same body: same answer; other body: 409), under one lock so parallel retries cannot both pass |
| 6 | The service token protected only `/v1/decisions`; the screens used open endpoints | Every endpoint except `/healthz` (and the WebSocket) needs `X-Service-Token`. The browser never sees it: nginx (Docker) and Vite (development) add it, playing the bank's terminal network. Without Docker the API reads `.env` itself |

Rerun after these fixes (2026-11-19): engine tests 46/46, API tests 26/26, `demo-check` 10/10, red team still 4 of 10 (attempt 9 relabelled, see Known limits), bench p95 about 7 ms in-process, Docker stack checked (token added by nginx, WebSocket through the proxy).

### One clock for the API (2026-11-21)

Refactoring from the architecture review; the engine, weights, thresholds and scenario sets are unchanged.

- `services/api/clock.py`: every business time in the API (24 h windows, pause end, consent revocation, event log) comes from one clock. `ShiftedClock` (real time plus an offset) runs the app; `ManualClock` (moves only when told) runs tests and the red team.
- "Skip time" moves the clock forward instead of rewriting five tables of stored dates; "Reset demo" sets it back to real time. A new date column can no longer be forgotten by the time skip (the `decisions` table was, until 2026-11-19).
- `ALLOW_CLIENT_TIMESTAMP` is gone: a `timestamp` sent by any caller gets 422. `eval/redteam.py` replays several days by moving a manual clock; its results are identical (4 of 10).
- Responses and decision status carry `pause_seconds_left` by the server clock. The screens count down from it, so the timer stays right after a time skip.
- Engine latency is measured with `time.perf_counter`, not with the clock.
- Also fixed: a Telegram error (or a non-2xx answer) is now logged as `notify_failed` instead of `notify_sent`; FastAPI `on_event` replaced by `lifespan`; `reports/scorecard_tune.md` regenerated, it was left from before the freeze (now false pauses 0.0%, camera drop 3.3 pp, recall still 74.4%).

Rerun: engine tests 46/46, API tests 33/33, `demo-check` 10/10, red team 4 of 10 (same traces), bench p95 under 20 ms in-process, screens checked by hand (pause timer, time skip, expiry). The Docker stack was not rebuilt after this change.


### One decision lifecycle for the demo and the metrics (2026-11-21)

Refactoring from the architecture review, built test-first. The engine, weights, thresholds and scenario sets are unchanged.

- `services/api/lifecycle.py` owns every step of an operation: `submit`, `answer`, `release`, `confirm_fraud`, and the pause ending. It checks the balance, moves money, reports each transition to the event log and passes every pause or hold to the trusted-person notification. It fails open if the engine is down or slower than 500 ms.
- It reads customers, money and decisions through a ledger with two adapters: SQLite for the API, in memory for tests and evaluation (`services/api/ledger.py`). The HTTP routes in `main.py` only translate to and from it.
- `eval/evaluate.py` now replays scenarios through the same lifecycle. Before, it had its own copy of the ask / answer / stop rules, so the bug fixes of 2026-11-19 (balance check, pause end) existed only in the demo.
- Tests: `services/api/test_lifecycle.py` (14, the lifecycle through its own interface, in memory on a manual clock), the 33 HTTP tests unchanged, and `eval/test_metrics_parity.py` (3), which checks the frozen holdout numbers from `reports/scorecard.md` and the tune numbers from `reports/FREEZE.md` through the lifecycle. `python tasks.py test-integration` runs all of them.
- **Holdout: identical.** All 180 scenarios, with and without the camera, give the same result field by field as the old replay; the rendered holdout scorecard is byte-identical to `reports/scorecard.md` (checked without adding a line to `holdout_runs.log`).
- **Tune set, without the camera: one scenario changed.** In `tune_savings_no_loan_006` the customer withdraws 423 000 + 262 000 + 454 000 of 1 517 000, then asks for 421 000 with 378 000 left. The old replay had no balance check and counted that impossible withdrawal as an engine stop. Now the bank refuses it for lack of money and it is not a stop. Tune recall without the camera goes from 71.1% to 70.0%, so tune metric 7 (recall drop without camera) goes from 3.3 pp to 4.4 pp: still within the 5 pp minimum, still above the 3 pp target. `reports/scorecard_tune.md` is regenerated. The generator can produce withdrawals above the balance; the scenario files are not changed, because that would change the frozen holdout hash.

Rerun: engine tests 46/46; API, lifecycle and parity tests 50/50; `demo-check` 10/10; red team unchanged (4 of 10); bench p95 within target. Screens and the Docker stack were not re-checked by hand after this change (the HTTP interface is unchanged and covered by the 33 HTTP tests).

### Docker and screens re-checked (2026-11-22)

Docker stack rebuilt from commit `3139752` and the demo script walked through by hand at `http://localhost:8080`: ATM question (45) then hold on the second try (95, four reasons, simulated trusted-person notice), cash desk pause for Bolat (65), app pause for Aigerim (75), officer release with comment, and "skip time +24 h" expiring the app pause. No browser console errors. Tests before the rebuild: engine 46/46; API, lifecycle and parity 50/50; `demo-check` 10/10.

## 11. Rules v2: an attempt to close the red-team bypasses (2026-11-23)

**The demo and every number above still use the frozen v1 rules.** v2 is a separate, frozen rule file (`engine/rules.v2.yaml`); the API uses it only with `RULES_PATH=engine/rules.v2.yaml`.

Method, one commit per step (details in `reports/FREEZE_v2.md`):

1. New scenario types in `data/generate.py` for the bypasses (fresh loan sent to a known recipient or to companies; one withdrawal a day for several days) and honest look-alikes (a large transfer to family, a week of renovation payments). Operations carry `payee_company_age_days` (the bank can read a company's registration date from the state register). The v1 sets regenerate byte for byte.
2. New sets `tune2` (339 scenarios) and `holdout2` (226), holdout2 hash locked (tag `holdout2-frozen`) **before** any v2 rule was written.
3. New signals, active only in v2: S12 loan or closed-deposit money leaves by transfer (60% of the balance in 24 h), S13 drain over 7 days across more than one day, S14 recipient company registered < 180 days ago; the company discount S9 applies only to companies registered >= 365 days ago.
4. Tuned on tune2 only (`reports/tuning_v2.md`), frozen (tag `v2-frozen`), then measured **once** for each version on holdout2 (`reports/holdout2_runs.log`; a repeat is refused).

Holdout2 (86 fraud, 140 normal), measured once per version:

| Metric | v1 | v2 | Minimum |
|---|---:|---:|---:|
| Recall | 67.4% (57-76%) | **76.7%** (67-84%) | 75% |
| Recall without relying on the question | 57.0% | 59.3% | 60% |
| False interventions, normal | 3.6% | 4.3% | <= 10% |
| False pauses, normal | 1.4% | 2.1% | <= 3% |
| Money saved | 60.8% | 69.0% | 55% |
| Recall drop without camera | 4.7 pp | **7.0 pp (FAIL)** | <= 5 pp |
| Fairness gap by age | 2.1 pp | 3.2 pp | <= 8 pp |

By the bypass types on holdout2 (stopped with the question / by pause alone): loan sent to companies 4/2 -> **10/10** of 10; loan sent to a known recipient 0/0 -> 4/0 of 8 (only an honest answer stops it); a withdrawal a day 2/2 -> 2/1 of 8 (**no gain**). Older types lost a little by pause alone (ATM series after a loan 12 -> 10 of 14). The recall intervals overlap: on 86 fraud scenarios the gain is not proven.

Scripted red team with v2 (`python eval/redteam.py --v2`, `reports/redteam_v2.md`; shells are 40 days old, attempt 11 uses an 11-year-old company): **4 of 11 attempts still reach the goal.**

- Fixed: transfers to young companies (attempts 7, 8) are now held or paused at once.
- Still open: a known recipient (6) and an old company (11) get only the question (score 60, pause at 65), so a coached "no" passes; one 400 000 a day for six days (10) passes.
- **New:** "wait 25 hours, then withdraw" (5) was stopped by v1 and passes under v2, because tuning raised the pause threshold from 55 to 65.

The same author wrote the v2 rules, the v2 scenario types and both v2 sets; holdout2 guards against tuning to single scenarios, not against a shared idea of how scammers behave. Whether the demo moves to v2 is a separate decision.
