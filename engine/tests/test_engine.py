from datetime import datetime, timedelta

import pytest

from engine import Customer, Events, Operation, decide, load_rules
from engine.scoring import band, with_overrides
from engine.signals import Executed

NOW = datetime(2026, 11, 19, 14, 0)
from pathlib import Path
RULES = load_rules(Path(__file__).resolve().parents[1] / "rules.start.yaml")  # unit tests pin the starting weights


def op(typ="cash_withdrawal", amount=100_000, **kw):
    base = dict(op_id="op1", ts=NOW, channel="atm", type=typ, amount=amount)
    base.update(kw)
    return Operation(**base)


def cust(balance=1_000_000, median=30_000):
    return Customer("c1", balance, median)


def run(o, c=None, ev=None, hist=None, rules=RULES):
    return decide(o, c or cust(), ev or Events(), hist or [], rules)


def codes(d):
    return {r["signal"] for r in d.reasons}


# ---- S1 loan within 24h -------------------------------------------------
def test_s1_fires_within_24h():
    d = run(op(amount=10_000), ev=Events(loan_issued_at=NOW - timedelta(hours=3)))
    assert "S1" in codes(d)


def test_s1_boundary_exactly_24h_does_not_fire():
    d = run(op(amount=10_000), ev=Events(loan_issued_at=NOW - timedelta(hours=24)))
    assert "S1" not in codes(d)


def test_s1_loan_in_the_future_does_not_fire():
    d = run(op(amount=10_000), ev=Events(loan_issued_at=NOW + timedelta(hours=1)))
    assert "S1" not in codes(d)


# ---- S2 balance drain ---------------------------------------------------
def test_s2_fires_at_80_percent():
    d = run(op(amount=800_000), cust(balance=1_000_000))
    assert "S2" in codes(d)


def test_s2_does_not_fire_below_80_percent():
    d = run(op(amount=799_000), cust(balance=1_000_000))
    assert "S2" not in codes(d)


def test_s2_counts_previous_executed_operations():
    hist = [Executed(NOW - timedelta(hours=2), "cash_withdrawal", 500_000)]
    d = run(op(amount=350_000), cust(balance=1_000_000), hist=hist)
    assert "S2" in codes(d)


def test_s2_ignores_operations_older_than_24h():
    hist = [Executed(NOW - timedelta(hours=25), "cash_withdrawal", 700_000)]
    d = run(op(amount=200_000), cust(balance=1_000_000), hist=hist)
    assert "S2" not in codes(d)


# ---- S3 first large cash withdrawal -------------------------------------
def test_s3_fires_for_large_cash():
    d = run(op(amount=300_000), cust(balance=5_000_000, median=30_000))
    assert "S3" in codes(d)


def test_s3_needs_300k_floor():
    d = run(op(amount=299_000), cust(balance=5_000_000, median=1_000))
    assert "S3" not in codes(d)


def test_s3_needs_5x_median():
    d = run(op(amount=300_000), cust(balance=5_000_000, median=70_000))
    assert "S3" not in codes(d)


def test_s3_not_for_transfers():
    d = run(op("transfer", 500_000, payee_known=True, channel="app"), cust(balance=5_000_000))
    assert "S3" not in codes(d)


# ---- S4 series ----------------------------------------------------------
def test_s4_fires_on_second_withdrawal_over_1m_total():
    hist = [Executed(NOW - timedelta(minutes=10), "cash_withdrawal", 500_000)]
    d = run(op(amount=500_000), cust(balance=9_000_000), hist=hist)
    assert "S4" in codes(d)


def test_s4_not_for_single_withdrawal():
    d = run(op(amount=1_200_000, channel="cash_desk"), cust(balance=9_000_000))
    assert "S4" not in codes(d)


def test_s4_not_below_1m_total():
    hist = [Executed(NOW - timedelta(minutes=10), "cash_withdrawal", 400_000)]
    d = run(op(amount=500_000), cust(balance=9_000_000), hist=hist)
    assert "S4" not in codes(d)


# ---- S5 / S6 / S7 -------------------------------------------------------
def test_s5_new_payee():
    d = run(op("transfer", 250_000, channel="app", payee_known=False), cust(balance=9_000_000))
    assert "S5" in codes(d)


def test_s5_known_payee_does_not_fire():
    d = run(op("transfer", 250_000, channel="app", payee_known=True), cust(balance=9_000_000))
    assert "S5" not in codes(d)


def test_s5_below_threshold_does_not_fire():
    d = run(op("transfer", 199_000, channel="app", payee_known=False), cust(balance=9_000_000))
    assert "S5" not in codes(d)


def test_s6_deposit_closed():
    d = run(op("transfer", 10_000, channel="app", payee_known=True), cust(balance=9_000_000),
            ev=Events(deposit_closed_early_at=NOW - timedelta(hours=1)))
    assert "S6" in codes(d)


def test_s7_combination_adds_bonus():
    d = run(op("transfer", 300_000, channel="app", payee_known=False), cust(balance=9_000_000),
            ev=Events(deposit_closed_early_at=NOW - timedelta(hours=1)))
    assert {"S5", "S6", "S7"} <= codes(d)
    assert d.score == 15 + 20 + 15


def test_s7_not_without_both():
    d = run(op("transfer", 300_000, channel="app", payee_known=False), cust(balance=9_000_000))
    assert "S7" not in codes(d)


# ---- S8 / S9 / S10 ------------------------------------------------------
def test_s8_report_button():
    d = run(op(amount=10_000), ev=Events(report_at=NOW - timedelta(hours=2)))
    assert "S8" in codes(d)
    assert d.decision == "ask"


def test_s9_legal_payee_reduces_score():
    kw = dict(channel="app", payee_known=False)
    legal = run(op("transfer", 400_000, payee_type="legal", **kw), cust(balance=9_000_000))
    person = run(op("transfer", 400_000, payee_type="individual", **kw), cust(balance=9_000_000))
    assert person.score - legal.score == 15
    assert legal.score == 0


def test_s10_camera_threshold():
    on = run(op(amount=10_000, phone_at_ear_sec=3.5))
    off = run(op(amount=10_000, phone_at_ear_sec=3.0))
    assert "S10" in codes(on) and "S10" not in codes(off)


def test_camera_disabled_ignores_s10():
    r = with_overrides(RULES, camera_enabled=False)
    assert "S10" not in codes(run(op(amount=10_000, phone_at_ear_sec=30), rules=r))


# ---- scoring, bands, explainability -------------------------------------
@pytest.mark.parametrize("score,expected", [
    (0, "allow"), (39, "allow"), (40, "ask"), (59, "ask"),
    (60, "pause"), (84, "pause"), (85, "hold"), (100, "hold"),
])
def test_band_boundaries(score, expected):
    assert band(score, RULES["thresholds"]) == expected


def test_score_is_clamped_to_100():
    ev = Events(loan_issued_at=NOW - timedelta(hours=1), report_at=NOW - timedelta(hours=1))
    hist = [Executed(NOW - timedelta(minutes=5), "cash_withdrawal", 800_000)]
    d = run(op(amount=900_000, phone_at_ear_sec=9), cust(balance=1_500_000), ev=ev, hist=hist)
    assert d.score == 100 and d.decision == "hold"


def test_score_never_negative():
    d = run(op("transfer", 250_000, channel="app", payee_type="legal"), cust(balance=9_000_000))
    assert d.score >= 0


def test_ordinary_withdrawal_is_allowed_without_reasons():
    d = run(op(amount=20_000))
    assert d.decision == "allow" and d.score == 0 and d.reasons == []


def test_phone_at_atm_alone_is_not_enough():
    """Ordinary person on the phone withdrawing 20k must not be bothered."""
    d = run(op(amount=20_000, phone_at_ear_sec=30))
    assert d.decision == "allow" and d.score == 10


def test_every_non_allow_decision_has_reasons():
    cases = [
        run(op(amount=500_000), cust(balance=5_000_000),
            ev=Events(loan_issued_at=NOW - timedelta(hours=3))),
        run(op("transfer", 300_000, channel="app"), cust(balance=9_000_000),
            ev=Events(deposit_closed_early_at=NOW - timedelta(hours=1))),
    ]
    for d in cases:
        assert d.decision != "allow"
        assert d.reasons and all(r["text_ru"] for r in d.reasons)


def test_reason_contributions_sum_to_score():
    d = run(op(amount=500_000), cust(balance=5_000_000),
            ev=Events(loan_issued_at=NOW - timedelta(hours=3)))
    assert sum(r["contribution"] for r in d.reasons) == d.score


# ---- demo scenarios from the plan (section 5) ---------------------------
def test_scenario_b_first_withdrawal_asks_second_pauses():
    ev = Events(loan_issued_at=NOW - timedelta(hours=3))
    c = cust(balance=3_000_000, median=30_000)
    first = decide(op(amount=500_000), c, ev, [], RULES)
    assert first.score == 50 and first.decision == "ask"
    hist = [Executed(NOW - timedelta(minutes=2), "cash_withdrawal", 500_000)]
    second = decide(op(amount=500_000, terminal_id="atm_2"), c, ev, hist, RULES)
    assert second.score == 70 and second.decision == "pause"


def test_scenario_c_cash_desk_pauses_at_70():
    d = run(op(amount=2_500_000, channel="cash_desk"), cust(balance=2_900_000),
            ev=Events(loan_issued_at=NOW - timedelta(hours=3)))
    assert d.score == 70 and d.decision == "pause"


def test_scenario_d_deposit_close_transfer_pauses():
    d = run(op("transfer", 2_000_000, channel="app", payee_type="individual"),
            cust(balance=2_000_000), ev=Events(deposit_closed_early_at=NOW - timedelta(hours=1)))
    assert d.decision == "pause"


def test_overrides_do_not_mutate_original():
    r = with_overrides(RULES, weights={"S1": 99}, thresholds={"ask": 10})
    assert RULES["weights"]["S1"] == 35 and RULES["thresholds"]["ask"] == 40
    assert r["weights"]["S1"] == 99


# ---- S11 escalation -----------------------------------------------------
def test_s11_fires_after_a_question_was_answered_no():
    hist = [Executed(NOW - timedelta(minutes=20), "cash_withdrawal", 100_000, asked=True)]
    d = run(op(amount=50_000), cust(balance=9_000_000), hist=hist)
    assert "S11" in codes(d) and d.score == 20


def test_s11_not_without_a_prior_question():
    hist = [Executed(NOW - timedelta(minutes=20), "cash_withdrawal", 100_000, asked=False)]
    assert "S11" not in codes(run(op(amount=50_000), cust(balance=9_000_000), hist=hist))


def test_s11_not_after_window():
    hist = [Executed(NOW - timedelta(hours=30), "cash_withdrawal", 100_000, asked=True)]
    assert "S11" not in codes(run(op(amount=50_000), cust(balance=9_000_000), hist=hist))


def test_scenario_b_with_escalation_pauses_with_margin():
    ev = Events(loan_issued_at=NOW - timedelta(hours=3))
    c = cust(balance=3_000_000, median=30_000)
    hist = [Executed(NOW - timedelta(minutes=2), "cash_withdrawal", 300_000, asked=True)]
    d = decide(op(amount=300_000), c, ev, hist, RULES)
    assert {"S1", "S3", "S11"} <= codes(d)
