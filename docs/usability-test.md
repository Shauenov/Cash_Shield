# Usability test: the pause screen (metric 15)

**Question:** when a customer sees the pause screen, do they do the right thing within 20 seconds, without any explanation?

**Pass rule (set before the test, do not change it afterwards):**

| | Target | Minimum |
|---|---|---|
| People who do the right thing within 20 seconds | 8 of 10 | 7 of 10 |
| People over 50 among the 10 | at least 3 | at least 3 |

If the result is below the minimum: rewrite the text, then repeat with 5 new people. Do not drop participants after the fact.

**Time needed:** about 5 minutes per person, 50 minutes for 10 people. Test alone, in one afternoon.

## 1. Who to recruit

- 10 adults who use a bank card or banking app. Not teammates, not people who have seen the demo.
- **At least 3 of the 10 over 50.** Try for a mix of Kazakh and Russian speakers; test each person in the language they choose.
- Tell them: "5 minutes, a short test of a banking screen. There are no wrong answers about you; we are testing the screen." Do not mention fraud or scams in advance.
- Verbal consent only: "May I note your age group, your answer and how long it took? I will not write your name or record you. You can stop at any time." If they say no, thank them and pick someone else.

## 2. Setup (once, before the first person)

1. Start the stack (`docker compose up`) and open `http://localhost:8080/#app`.
   - Better on a phone: on the same Wi-Fi open `http://<laptop IP>:8080/#app` on a phone and hand the phone over. (You may need to allow port 8080 in the Windows firewall.)
2. Pick the customer **Aigerim**. Leave the transfer at **2000000 / Private person**.
3. Before each person: open `http://localhost:8080/#officer`, click **Reset demo**, go back to `#app`, choose Aigerim, press **Transfer** yourself so the pause screen is showing, then pass the device.
   - Set the language the participant chose with the **EN / KZ / RU** buttons *before* handing it over.
4. Have a stopwatch ready and a printed copy of the sheet in section 5 (or fill the CSV directly).

## 3. What you say (read it exactly, do not add anything)

> "Imagine you are at your bank. Someone phoned you, said they are from the bank and told you to take out money to keep it safe. You tried to send it from this app, and this is what you now see. Please tell me, or show me, what you would do now. Take your time but speak out loud."

Russian (read it exactly):

> «Представьте, что вы в своём банке. Вам позвонили, сказали, что звонят из банка, и велели перевести деньги, чтобы их сохранить. Вы попробовали отправить их из этого приложения и теперь видите вот это. Скажите или покажите, пожалуйста, что вы сейчас сделаете. Не торопитесь, но говорите вслух.»

Kazakh: not prepared yet. Have a native speaker translate the English text before the test and write it here; do not translate on the spot, every person must hear the same words.

Before handing the device over, scroll so that the pause screen fills the view. The page header and the tabs above it ("Scammer", "Trusted person") are English demo labels and can hint at the answer; if a participant reads them, note it.

Start the stopwatch when you finish the last word and the person looks at the screen. Stop it when they say or do something that you can score (section 4).

During the test:

- Do not explain, point, or read the screen for them.
- If they ask "what should I do?": "What would you do if this were real?"
- If they ask what a word means: "What do you think it means?" and write the word down.
- After 20 seconds with no scorable action, stop the clock and mark it as no action.

## 4. Scoring rule (fixed before the test)

**Correct** (and within 20 seconds): the person
- says they will **not** withdraw or give the money to anyone, **or**
- says they will **not** do what the caller told them and will contact the bank themselves, **or**
- presses **"Call the bank from the app"** (or its Russian or Kazakh text).

**Not correct:**
- Waits for the timer and says they will try again afterwards.
- Says they will call the number the caller gave, or asks the caller what to do.
- Says "OK" or does nothing, or cannot say what the screen wants.
- Says they would ignore the screen.
- Correct, but only after 20 seconds.

Write down the exact words. When unsure, mark **not correct** and add a note. Do not re-score after seeing the totals.

## 5. Observation sheet (one row per person, no names)

| # | Age group (18–34 / 35–50 / over 50) | Language | Seconds to first scorable action | What they said or did | Correct? (Y/N) | Words or lines they did not understand | Notes |
|---|---|---|---:|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |
| 7 | | | | | | | |
| 8 | | | | | | | |
| 9 | | | | | | | |
| 10 | | | | | | | |

After the task, ask each person two quick questions and note the answers in the Notes column:
1. "In your own words, what is this screen telling you?"
2. "Is there a word or sentence that was unclear or sounded strange?" (This is also a cheap check of the Kazakh and Russian wording.)

## 6. After the 10 people

1. Copy the rows into `reports/usability_data.csv` (columns are already there; use `Y` or `N`, and `over 50` for the oldest group).
2. Run `python tasks.py usability`. It writes `reports/usability.md` with the result against the pass rule and the list of unclear words.
3. If it is FAIL or below target: change the text, write the change in the README, and test 5 new people. Keep the first result in the report.

## 7. What this test cannot tell you

- It is a quiet room, not a person under phone pressure. A coached victim may behave very differently.
- 10 people give a coarse number: 8 of 10 has a 95% interval of roughly 49% to 94%.
- The Kazakh and Russian texts are the team's, not reviewed by a native-speaker editor. Unclear words from this test are the first input for that review.
