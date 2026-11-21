"""Automated rehearsal of the 3-minute demo, at API level (no screens, no camera, no Telegram).

Runs the demo storyline N times, resetting state before each run, and checks every
expected decision. This is NOT the manual 10-of-10 protocol of the plan (that one
needs the real screens and a person); it only shows the backend part is repeatable.

Run: python eval/demo_check.py [N]     -> writes reports/demo_runs.md
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from services.api import main  # noqa: E402

main.DEMO_MODE = True   # uses demo-reset / engine-down
client = TestClient(main.app, headers={"X-Service-Token": main.SERVICE_TOKEN})
n = [0]


def op(cid, amount, channel="atm", typ="cash_withdrawal", **kw):
    n[0] += 1
    b = dict(operation_id=f"demo{n[0]}", customer_id=cid, channel=channel, type=typ, amount_kzt=amount)
    b.update(kw)
    return client.post("/mock-host/authorize", json=b).json()


def events():
    return [e["kind"] for e in client.get("/v1/events").json()]


def one_run():
    """Returns (rows, error). rows: list of (step, observed, expected, ok)."""
    client.post("/v1/demo-reset")
    rows = []

    def check(step, observed, expected):
        rows.append((step, observed, expected, observed == expected))

    # 1. Gulnar apa at ATM 017: first withdrawal asks the question, answer "no", cash dispensed
    r = op("c_gulnar", 500_000, terminal_id="atm_017")
    check("1 ATM 017, 500k: decision", r["decision"], "ask")
    check("1 score", r["score"], 45)
    a = client.post(f"/v1/decisions/{r['decision_id']}/answer", json={"answer": "no"}).json()
    check("1 answer no -> cash", a["result"], "approve")

    # 2. Second withdrawal at ATM 042, camera off: held, trusted person notified
    r = op("c_gulnar", 500_000, terminal_id="atm_042")
    check("2 ATM 042, 500k, camera off: decision", r["decision"], "hold")
    check("2 score", r["score"], 95)
    check("2 reasons include S11", "S11" in [x["signal"] for x in r["reasons"]], True)
    check("2 trusted person notified", "notify_sent" in events(), True)
    held_gulnar = r["decision_id"]

    # 3. Cash desk, Bolat 2.5M: pause, no consent -> no message
    r = op("c_bolat", 2_500_000, channel="cash_desk", terminal_id="desk_01")
    check("3 cash desk 2.5M: decision", r["decision"], "pause")
    check("3 score", r["score"], 65)
    check("3 no consent -> no message", "notify_skipped_no_consent" in events(), True)
    bolat = r["decision_id"]

    # 4. App, Aigerim: close deposit + transfer to a new person: pause
    r = op("c_aigerim", 2_000_000, channel="app", typ="transfer", payee_id="p_9",
           payee_type="individual", payee_known=False)
    check("4 app transfer: decision", r["decision"], "pause")
    check("4 score", r["score"], 75)

    # 5. Officer releases Bolat (false alarm), confirms Gulnar's as fraud
    rel = client.post(f"/v1/decisions/{bolat}/override", headers={"X-Officer-Id": "o_01"},
                      json={"action": "release", "comment": "Bought a car, confirmed by phone"}).json()
    check("5 officer release (false alarm)", rel["result"], "approve")
    fr = client.post(f"/v1/decisions/{held_gulnar}/override", headers={"X-Officer-Id": "o_01"},
                     json={"action": "confirm_fraud", "comment": "Customer confirmed she was coached"}).json()
    check("5 officer confirm fraud", fr["result"], "decline")

    # 6. Control: Marat withdraws 20k, nothing happens
    r = op("c_marat", 20_000)
    check("6 control 20k: decision", r["decision"], "allow")

    # 7. Engine outage: host approves anyway
    client.post("/v1/demo-engine-down?down=true")
    r = op("c_dana", 50_000)
    check("7 engine down -> approve", r["result"], "approve")
    client.post("/v1/demo-engine-down?down=false")
    return rows


def main_():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    ok_runs, first_fail, steps = 0, None, 0
    for i in range(runs):
        rows = one_run()
        steps = len(rows)
        bad = [r for r in rows if not r[3]]
        if not bad:
            ok_runs += 1
        elif first_fail is None:
            first_fail = (i + 1, bad)
    lines = ["# Demo rehearsal (API level, automated)", "",
             f"{ok_runs} of {runs} runs passed, {steps} checks per run, frozen rules.", "",
             "Covers: decisions, scores, trusted-person notification (simulated), officer actions, "
             "fail-open. Does NOT cover: the screens, the camera switch, real Telegram, a live audience.", ""]
    if first_fail:
        lines += [f"First failing run: {first_fail[0]}"] + [f"- {s}: got {o!r}, expected {e!r}" for s, o, e, _ in first_fail[1]]
    else:
        lines += ["Checks per run:"] + [f"- {s}: {e!r}" for s, _, e, _ in rows]
    text = "\n".join(lines) + "\n"
    (ROOT / "reports" / "demo_runs.md").write_text(text, encoding="utf-8")
    print(text)
    sys.exit(0 if ok_runs == runs else 1)


if __name__ == "__main__":
    main_()
