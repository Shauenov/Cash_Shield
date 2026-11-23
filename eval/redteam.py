"""Scripted red team against the running API logic (in-process, fresh state per attempt).

Goal for the attacker: move >= 2 000 000 KZT of a customer's money out WITHOUT the
operation being paused or held. The attacker behaves like a coached victim: on every
question the answer is "no". Money that went through before a hold counts as lost.

Honest caveat: the author of this script also wrote the rules, so this is NOT a blind
test. A blind red team (someone who only sees the screens) is still to be done.
Run: python eval/redteam.py        -> writes reports/redteam.md (frozen v1 rules)
     python eval/redteam.py --v2   -> writes reports/redteam_v2.md (engine/rules.v2.yaml).
     Under v2 the shells in attempts 7 and 8 are 40 days old, and attempt 11 uses a company
     registered 11 years ago (a bought or hijacked old firm).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
V2 = "--v2" in sys.argv
if V2:   # must be set before the API module reads its rules
    os.environ["RULES_PATH"] = str(ROOT / "engine" / "rules.v2.yaml")
SHELL = {"payee_company_age_days": 40} if V2 else {}

from fastapi.testclient import TestClient  # noqa: E402
from services.api import main  # noqa: E402
from services.api.clock import TZ, ManualClock  # noqa: E402

GOAL = 2_000_000
main.DEMO_MODE = True               # uses demo-reset
client = TestClient(main.app, headers={"X-Service-Token": main.SERVICE_TOKEN})
n = [0]


def attempt(customer, steps, title, idea):
    """steps: list of (minutes_from_start, channel, type, amount, extra_fields).
    Several days are replayed by moving a manual clock; the host stamps every operation itself."""
    base = datetime.now(TZ).replace(microsecond=0)
    main.CLOCK = ManualClock(base)
    client.post("/v1/demo-reset")
    out, moved, stopped_at, trace = 0, 0, None, []
    for minutes, channel, typ, amount, extra in steps:
        n[0] += 1
        main.CLOCK.set(base + timedelta(minutes=minutes))
        body = dict(operation_id=f"rt{n[0]}", customer_id=customer, channel=channel, type=typ,
                    amount_kzt=amount, terminal_id=f"atm_{n[0] % 50:03d}")
        body.update(extra)
        r = client.post("/mock-host/authorize", json=body).json()
        d = r["decision"]
        if r["result"] == "ask":
            client.post(f"/v1/decisions/{r['decision_id']}/answer", json={"answer": "no"})  # coached
            moved += amount
            trace.append(f"{amount // 1000}k:{d}({r['score']})->no")
        elif r["result"] == "approve":
            moved += amount
            trace.append(f"{amount // 1000}k:{d}({r['score']})")
        elif d == "insufficient_funds":
            # the host refused for lack of money: not an engine stop
            stopped_at = f"op {len(trace) + 1} (no funds)"
            trace.append(f"{amount // 1000}k:insufficient_funds->NO FUNDS, not an engine stop")
            break
        else:
            stopped_at = f"op {len(trace) + 1}"
            trace.append(f"{amount // 1000}k:{d}({r['score']})->STOP")
            break
    success = stopped_at is None and moved >= GOAL
    return dict(title=title, idea=idea, customer=customer, moved=moved, stopped=stopped_at,
                success=success, trace=" ".join(trace))


def run():
    A = []
    A.append(attempt("c_gulnar", [(0, "cash_desk", "cash_withdrawal", 2_500_000, {})],
                     "1. Straight cash-desk withdrawal", "Take almost everything in one go"))
    A.append(attempt("c_gulnar", [(i * 12, "atm", "cash_withdrawal", 500_000, {}) for i in range(5)],
                     "2. Five ATM withdrawals of 500k", "Use the ATM limit, answer 'no' to the question"))
    A.append(attempt("c_gulnar", [(i * 20, "atm", "cash_withdrawal", 250_000, {}) for i in range(9)],
                     "3. Nine withdrawals of 250k", "Stay below the 'large cash' threshold"))
    A.append(attempt("c_gulnar", [(i * 45, "atm", "cash_withdrawal", 200_000, {}) for i in range(11)],
                     "4. Slow drip, 200k every 45 min", "Spread over hours to look ordinary"))
    A.append(attempt("c_gulnar", [(25 * 60 + i * 15, "atm", "cash_withdrawal", 500_000, {}) for i in range(5)],
                     "5. Wait 25 hours, then withdraw", "Let the 24-hour 'fresh loan' signal expire"))
    A.append(attempt("c_gulnar", [(0, "app", "transfer", 2_200_000,
                                   dict(payee_id="p_1", payee_type="individual", payee_known=True))],
                     "6. Transfer to a recipient already known", "Make the recipient look familiar"))
    A.append(attempt("c_gulnar", [(0, "app", "transfer", 2_200_000,
                                   dict(payee_id="p_2", payee_type="legal", payee_known=False, **SHELL))],
                     "7. Transfer to a company (shell firm)", "Use the company discount (S9)"))
    A.append(attempt("c_gulnar", [(0, "app", "transfer", 700_000,
                                   dict(payee_id="p_3", payee_type="legal", payee_known=False, **SHELL)),
                                  (30, "app", "transfer", 700_000,
                                   dict(payee_id="p_4", payee_type="legal", payee_known=False, **SHELL)),
                                  (60, "app", "transfer", 700_000,
                                   dict(payee_id="p_5", payee_type="legal", payee_known=False, **SHELL))],
                     "8. Three transfers to three companies", "Split across recipients and shells"))
    A.append(attempt("c_dana", [(0, "cash_desk", "cash_withdrawal", 500_000, {}),
                                (400, "cash_desk", "cash_withdrawal", 500_000, {})],
                     "9. Customer with no loan, normal cash", "Plain savings, no loan, no deposit"))
    A.append(attempt("c_bolat", [(0, "atm", "cash_withdrawal", 400_000, {}),
                                 (24 * 60 + 5, "atm", "cash_withdrawal", 400_000, {}),
                                 (48 * 60 + 10, "atm", "cash_withdrawal", 400_000, {}),
                                 (72 * 60 + 15, "atm", "cash_withdrawal", 400_000, {}),
                                 (96 * 60 + 20, "atm", "cash_withdrawal", 400_000, {}),
                                 (120 * 60 + 25, "atm", "cash_withdrawal", 400_000, {})],
                     "10. One 400k per day for six days", "Stay under every 24-hour window"))
    if V2:
        A.append(attempt("c_gulnar", [(0, "app", "transfer", 2_200_000,
                                       dict(payee_id="p_6", payee_type="legal", payee_known=False,
                                            payee_company_age_days=4000))],
                         "11. Transfer to an old company", "Use a firm registered 11 years ago"))
    return A


def money(x):
    return f"{x:,}".replace(",", " ")


def render(A):
    lines = ["# Red team log", "",
             "Goal: move >= 2 000 000 KZT out without a pause or hold. The attacker answers 'no' to every question.",
             (f"Run with `python eval/redteam.py --v2` against `engine/rules.v2.yaml` (`v2-frozen`)." if V2 else
              "Run with `python eval/redteam.py` against the frozen rules (`thresholds-frozen`)."), "",
             "**Honest caveat:** the same person wrote the rules and these attempts, so this is not a blind test. "
             "A second person who sees only the screens still has to try.", "",
             "| # | Attempt | Idea | Money moved before stop | Stopped | Goal reached |",
             "|---|---|---|---:|---|---|"]
    for a in A:
        lines.append(f"| {a['title']} | {a['idea']} | {money(a['moved'])} | {a['stopped'] or 'never'} | "
                     f"{'**YES (bypass)**' if a['success'] else 'no'} |")
    lines += ["", "## Traces (amount: decision(score), -> answer)", ""]
    for a in A:
        lines.append(f"- {a['title']}: `{a['trace']}`")
    ok = [a for a in A if a["success"]]
    lines += ["", f"## Result: {len(ok)} of {len(A)} attempts reached the goal", ""]
    for a in ok:
        lines.append(f"- {a['title']}: moved {money(a['moved'])} KZT without a stop.")
    lines += ["", "Findings are not fixed by tuning the weights after the holdout measurement. "
              "They go into the README limits and the answers to the jury.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    res = run()
    text = render(res)
    (ROOT / "reports" / ("redteam_v2.md" if V2 else "redteam.md")).write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
