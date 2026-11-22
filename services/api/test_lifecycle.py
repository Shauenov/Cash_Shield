"""Decision lifecycle, tested through its own interface (seam 1).

In memory, on a manual clock, with the frozen rules. No HTTP, no SQL.
Expected values are worked by hand from the rules in engine/rules.yaml.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.api.clock import TZ, ManualClock  # noqa: E402
from services.api.ledger import InMemoryLedger  # noqa: E402
from services.api.lifecycle import Lifecycle, OpRequest  # noqa: E402

T0 = datetime(2030, 1, 1, 12, 0, tzinfo=TZ)


def setup(**customers):
    """customers: cid -> dict(balance=..., median=..., loan_h_ago=..., deposit_h_ago=...)."""
    clock = ManualClock(T0)
    ledger = InMemoryLedger()
    for cid, c in customers.items():
        ledger.add_customer(
            cid, balance=c["balance"], median_withdrawal=c.get("median", 25_000),
            loan_issued_at=T0 - timedelta(hours=c["loan_h_ago"]) if "loan_h_ago" in c else None,
            deposit_closed_at=T0 - timedelta(hours=c["deposit_h_ago"]) if "deposit_h_ago" in c else None)
    return Lifecycle(ledger, clock), ledger, clock


_n = [0]


def op(cid, amount, channel="atm", typ="cash_withdrawal", **kw):
    _n[0] += 1
    return OpRequest(operation_id=f"op{_n[0]}", customer_id=cid, channel=channel, type=typ,
                     amount=amount, **kw)


def test_ordinary_withdrawal_is_approved_and_money_moves():
    lc, ledger, _ = setup(marat=dict(balance=800_000))
    out = lc.submit(op("marat", 20_000))
    assert out.result == "approve" and out.decision == "allow"
    assert ledger.balance("marat") == 780_000


def test_amount_above_balance_is_declined_and_nothing_moves():
    lc, ledger, _ = setup(marat=dict(balance=800_000))
    out = lc.submit(op("marat", 5_000_000))
    assert out.result == "decline" and out.decision == "insufficient_funds"
    assert ledger.balance("marat") == 800_000 and ledger.history("marat") == []


GULNAR = dict(balance=3_000_000, median=30_000, loan_h_ago=3)


def test_answer_no_lets_money_go_and_the_next_attempt_escalates():
    lc, ledger, _ = setup(gulnar=GULNAR)
    first = lc.submit(op("gulnar", 500_000))
    assert (first.result, first.score) == ("ask", 45)          # S1 30 + S3 15
    assert lc.answer(first.decision_id, yes=False).result == "approve"
    assert ledger.balance("gulnar") == 2_500_000
    second = lc.submit(op("gulnar", 500_000))
    assert (second.result, second.decision, second.score) == ("hold", "hold", 95)   # + S4 30 + S11 20
    assert "S11" in [r["signal"] for r in second.reasons]
    assert ledger.balance("gulnar") == 2_500_000


def test_answer_yes_pauses_for_thirty_minutes_and_nothing_moves():
    lc, ledger, _ = setup(gulnar=GULNAR)
    first = lc.submit(op("gulnar", 500_000))
    out = lc.answer(first.decision_id, yes=True)
    assert (out.result, out.decision) == ("hold", "pause")
    assert out.pause_seconds_left == 1800
    assert lc.status(first.decision_id) == "held"
    assert ledger.balance("gulnar") == 3_000_000


AIGERIM = dict(balance=2_000_000, median=20_000, deposit_h_ago=1)


def test_engine_pause_ends_after_thirty_minutes_and_nothing_moves():
    lc, ledger, clock = setup(aigerim=AIGERIM)
    out = lc.submit(op("aigerim", 2_000_000, channel="app", typ="transfer", payee_type="individual"))
    assert (out.result, out.decision, out.score) == ("hold", "pause", 75)   # S2 20 + S5 15 + S6 20 + S7 20
    assert out.pause_seconds_left == 1800
    clock.advance(timedelta(minutes=29))
    assert lc.status(out.decision_id) == "held"
    clock.advance(timedelta(minutes=2))
    assert lc.status(out.decision_id) == "expired"
    assert ledger.balance("aigerim") == 2_000_000


import pytest  # noqa: E402
from services.api.lifecycle import Conflict  # noqa: E402

BOLAT = dict(balance=2_900_000, median=30_000, loan_h_ago=3)


def test_officer_release_moves_the_money_once():
    lc, ledger, _ = setup(bolat=BOLAT)
    out = lc.submit(op("bolat", 2_500_000, channel="cash_desk"))
    assert (out.decision, out.score) == ("pause", 65)          # S1 30 + S2 20 + S3 15
    assert lc.release(out.decision_id, officer="o_01", comment="bought a car").result == "approve"
    assert ledger.balance("bolat") == 400_000
    with pytest.raises(Conflict):
        lc.release(out.decision_id, officer="o_01", comment="again")
    assert ledger.balance("bolat") == 400_000


def test_hold_waits_for_the_officer_and_release_rechecks_the_balance():
    lc, ledger, clock = setup(gulnar=GULNAR)
    first = lc.submit(op("gulnar", 500_000))
    lc.answer(first.decision_id, yes=False)
    held = lc.submit(op("gulnar", 500_000))
    clock.advance(timedelta(hours=2))
    assert lc.status(held.decision_id) == "held"
    ledger.execute("gulnar", clock.now(), "transfer", 2_200_000, False)   # balance now 300 000
    with pytest.raises(Conflict):
        lc.release(held.decision_id, officer="o_01", comment="customer confirmed")
    assert ledger.balance("gulnar") == 300_000 and lc.status(held.decision_id) == "held"


def test_confirmed_fraud_is_declined_and_cannot_be_released():
    lc, ledger, _ = setup(bolat=BOLAT)
    out = lc.submit(op("bolat", 2_500_000, channel="cash_desk"))
    assert lc.confirm_fraud(out.decision_id, officer="o_01", comment="victim confirmed coaching").result == "decline"
    assert lc.status(out.decision_id) == "declined"
    with pytest.raises(Conflict):
        lc.release(out.decision_id, officer="o_01", comment="changed my mind")
    assert ledger.balance("bolat") == 2_900_000


def test_a_question_is_answered_once():
    lc, ledger, _ = setup(gulnar=GULNAR)
    first = lc.submit(op("gulnar", 500_000))
    lc.answer(first.decision_id, yes=False)
    with pytest.raises(Conflict):
        lc.answer(first.decision_id, yes=False)
    assert ledger.balance("gulnar") == 2_500_000


def test_answer_no_rechecks_the_balance():
    lc, ledger, clock = setup(gulnar=GULNAR)
    first = lc.submit(op("gulnar", 500_000))
    ledger.execute("gulnar", clock.now(), "transfer", 2_700_000, False)   # balance now 300 000
    with pytest.raises(Conflict):
        lc.answer(first.decision_id, yes=False)
    assert ledger.balance("gulnar") == 300_000 and lc.status(first.decision_id) == "open"


def recorder():
    seen, told = [], []
    return seen, told, (lambda kind, rec, actor, comment: seen.append(kind)), (lambda rec: told.append(rec["decision_id"]))


def test_every_transition_is_reported_once_and_relatives_hear_only_of_stops():
    seen, told, events, notify = recorder()
    lc, ledger, clock = setup(gulnar=GULNAR, aigerim=AIGERIM, marat=dict(balance=800_000))
    lc.events, lc.notify = events, notify
    lc.submit(op("marat", 5_000_000))                               # insufficient_funds
    first = lc.submit(op("gulnar", 500_000))                        # decision (ask)
    lc.answer(first.decision_id, yes=False)                         # answer
    held = lc.submit(op("gulnar", 500_000))                         # decision (hold) + notify
    paused = lc.submit(op("aigerim", 2_000_000, channel="app", typ="transfer",
                          payee_type="individual"))                 # decision (pause) + notify
    clock.advance(timedelta(minutes=31))
    lc.status(paused.decision_id)
    lc.status(paused.decision_id)                                   # pause_expired, once
    lc.release(held.decision_id, officer="o_01", comment="called the customer")   # override
    assert seen == ["insufficient_funds", "decision", "answer", "decision", "decision",
                    "pause_expired", "override"]
    assert told == [held.decision_id, paused.decision_id]


@pytest.mark.parametrize("engine_fault", ["crash", "slow"])
def test_engine_fault_fails_open_and_is_logged(engine_fault):
    import time

    def broken(*_):
        if engine_fault == "crash":
            raise RuntimeError("engine down")
        time.sleep(0.5)

    seen, _, events, _ = recorder()
    lc, ledger, _ = setup(gulnar=GULNAR)
    lc.events, lc.engine, lc.timeout = events, broken, 0.05
    out = lc.submit(op("gulnar", 2_500_000, channel="cash_desk"))   # would be a pause with the engine up
    assert (out.result, out.engine_available) == ("approve", False)
    assert ledger.balance("gulnar") == 500_000
    assert seen == ["engine_unavailable"]


def test_unknown_decision_is_not_found():
    from services.api.lifecycle import NotFound
    lc, _, _ = setup(marat=dict(balance=800_000))
    for step in (lambda: lc.current("d_nope"), lambda: lc.answer("d_nope", yes=False),
                 lambda: lc.release("d_nope", officer="o", comment="x")):
        with pytest.raises(NotFound):
            step()
