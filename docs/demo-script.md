# Demo script (3 minutes)

All scores below come from the frozen rules and were checked by `python eval/demo_check.py` (10 of 10 automated runs at API level). They do not prove the screens or the live setup work: rehearse those by hand.

## Before you go on stage

1. `docker compose up` (or the non-Docker commands in the README). Wait until `http://localhost:8080` loads.
2. Two browser windows side by side:
   - **Left (customer side):** `http://localhost:8080/#atm`
   - **Right (bank side):** `http://localhost:8080/#officer`
3. In the right window click **Reset demo**. The stat tiles must show zeros.
4. Left window: customer **Gulnar apa**, amount **500000**, ATM **ATM 017**, camera **Off**.
   Language: the **EN / RU / KZ** buttons in the top bar switch the whole interface (the choice is kept). For a Russian pitch press **RU** in both windows: the labels below are the English ones (**Withdraw** = «Снять», **New operation** = «Новая операция», **Reset demo** = «Сбросить демо», **Release** = «Снять паузу»).
5. Open two more tabs in the left window for the cash desk (`#desk`) and the app (`#app`).
6. Telegram: if you want the daughter's phone to buzz, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_DEMO_CHAT_ID` in `.env`, restart, and keep a phone in hand. **Without them the message is only simulated** (the console shows "simulated: Daughter Aliya"): then do not say the phone buzzed.
7. Have the backup video and the slides PDF open on a second laptop.

## The 3-minute run

| Time | Screen | Do | Say | What the audience sees |
|---|---|---|---|---|
| 0:00–0:15 | ATM, Gulnar apa | Nothing yet | "Gulnar apa is a made-up customer. A caller from the National Bank told her to take a loan and withdraw cash. She is at the ATM now." | Balance 3 000 000 ₸ |
| 0:15–0:40 | ATM | Click **Withdraw 500 000 ₸**, then **No, this is my own decision** | "The scammer taught her to answer no. The cash comes out." | Question screen, then "Done. Please take your cash". Console: score 45, reasons S1 and S3 |
| 0:40–1:10 | ATM | Click **New operation**, choose **ATM 042**, camera stays **Off**, click **Withdraw** | "Different ATM, below the limit. She already said no. The system still stops her." | Pause screen. Console: score 95 and four reasons, including "tries again after the question" |
| 1:10–1:30 | Console | Point at the `notify_sent` row (or the phone) | "She agreed in advance that her daughter is told. The message has no amount." | `notify_sent`, "simulated: Daughter Aliya" or a real Telegram message |
| 1:30–1:55 | Cash desk tab | Customer **Bolat**, **2500000**, click **Pay out** | "Large sums go through the cash desk. The same engine gives the cashier the reasons." | Score 65, three reasons, "Do not pay out", **Pass to officer** |
| 1:55–2:20 | App tab | Customer **Aigerim**, **2000000**, new **Private person**, click **Transfer** | "A closed deposit plus a transfer to a new person: the 'safe account' scheme." | Pause screen with "Call the bank from the app". Console score 75 |
| 2:20–2:40 | Console | In Bolat's card type **Bought a car, confirmed by phone**, click **Release pause** | "An honest customer is released by an officer in two clicks, with a comment on record." | "false alarms released" goes to 1 |
| 2:40–3:00 | Slides: scorecard | Show the scorecard slide | "On 180 synthetic scenarios, measured once: 78.3% of fraud stopped, 4.2% of normal customers bothered, none paused. We missed our 85% target, and a scripted red team got through in 4 of 10 tries. All commands are in the repo." | Scorecard and limits |

The first 500 000 ₸ in step 2 is lost on purpose. It shows why "money saved" is 71.5% and not 100%.

## If you only get 90 seconds for the demo

Keep rows 0:15–0:40, 0:40–1:10 and 2:20–2:40 (ATM question, ATM stop, officer release). Cut the cash desk and app, and mention them in one sentence.

## If something breaks

| What breaks | What to do |
|---|---|
| Screens do not load or stay empty | Play the backup video; say "this is the recorded run of the same flow" |
| Question screen never appears | Click **Reset demo** in the console, refresh, retry once. If it fails again, switch to the video |
| Stop does not appear on the second withdrawal | You skipped the answer "No" in step 2, or did not reset. Reset and repeat steps 1–2 |
| No Telegram message | Say it is simulated and point at the console row |
| Engine outage | Click **Simulate engine outage** in the console and withdraw: the host approves and logs it. This is the designed fail-open behaviour, say so |

## Optional extras (only if time allows)

- "Scammer on the line" button in the app tab, then a small withdrawal: the question appears (score 40).
- Trusted-person consent in the app tab, then withdraw consent: it only takes effect after 24 hours.

## Do not claim

- That the camera detects phones: it is a switch in this build.
- That Telegram worked, unless a message really arrived.
- That the numbers describe real customers: all data is synthetic.
- That the bank's real ATM host was used: it is a mock.
