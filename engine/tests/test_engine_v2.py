"""v2 signals (S12-S14) and the v2 company discount, against the starting v2 rules.

v1 rules have no S12-S14 weights, so these signals never run under v1: checked
at the end of this file and, on the frozen holdout, by eval/test_metrics_parity.py.
"""
from datetime import datetime, timedelta
from pathlib import Path

from engine import Customer, Events, Operation, decide, load_rules
from engine.signals import Executed

NOW = datetime(2026, 11, 23, 14, 0)
HERE = Path(__file__).resolve().parents[1]
V2 = load_rules(HERE / "rules.v2.start.yaml")
V1 = load_rules(HERE / "rules.start.yaml")
LOAN = Events(loan_issued_at=NOW - timedelta(hours=3))


def tr(amount, **kw):
    base = dict(op_id="op1", ts=NOW, channel="app", type="transfer", amount=amount,
                payee_id="p1", payee_type="individual", payee_known=False)
    base.update(kw)
    return Operation(**base)


def cash(amount, ts=NOW):
    return Operation(op_id="op1", ts=ts, channel="atm", type="cash_withdrawal", amount=amount)


def cust(balance=3_000_000, week=None):
    return Customer("c1", balance, 30_000, balance_7d_start=week)


def codes(d):
    return {r["signal"] for r in d.reasons}


# ---- S12 loan or deposit money leaving by transfer ------------------------
def test_s12_large_transfer_to_known_recipient_after_loan():
    d = decide(tr(2_200_000, payee_known=True), cust(), LOAN, [], V2)
    assert "S12" in codes(d)


def test_s12_counts_earlier_transfers_in_the_window():
    hist = [Executed(NOW - timedelta(hours=1), "transfer", 700_000),
            Executed(NOW - timedelta(minutes=30), "transfer", 700_000)]
    d = decide(tr(700_000, payee_type="legal", payee_company_age_days=2000), cust(), LOAN, hist, V2)
    assert "S12" in codes(d)


def test_s12_needs_a_loan_or_closed_deposit():
    d = decide(tr(2_200_000, payee_known=True), cust(), Events(), [], V2)
    assert "S12" not in codes(d)


def test_s12_small_share_does_not_fire():
    d = decide(tr(500_000, payee_known=True), cust(), LOAN, [], V2)
    assert "S12" not in codes(d)


# ---- S13 drain over seven days ----------------------------------------------
def _days(n, amount):
    return [Executed(NOW - timedelta(days=i), "cash_withdrawal", amount) for i in range(n, 0, -1)]


def test_s13_fires_on_a_daily_drip():
    d = decide(cash(400_000), cust(balance=1_000_000, week=3_000_000), Events(), _days(5, 400_000), V2)
    assert "S13" in codes(d)


def test_s13_does_not_fire_within_one_day():
    hist = [Executed(NOW - timedelta(hours=2), "cash_withdrawal", 1_500_000)]
    d = decide(cash(400_000), cust(balance=1_100_000, week=3_000_000), Events(), hist, V2)
    assert "S13" not in codes(d)


def test_s13_small_share_does_not_fire():
    d = decide(cash(100_000), cust(balance=2_600_000, week=3_000_000), Events(), _days(2, 150_000), V2)
    assert "S13" not in codes(d)


def test_s13_without_a_seven_day_balance_does_not_fire():
    d = decide(cash(400_000), cust(balance=1_000_000), Events(), _days(5, 400_000), V2)
    assert "S13" not in codes(d)


# ---- S14 young company and the v2 company discount -------------------------
def test_s14_young_company_and_no_discount():
    d = decide(tr(700_000, payee_type="legal", payee_company_age_days=40), cust(), Events(), [], V2)
    assert "S14" in codes(d) and "S9" not in codes(d)


def test_established_company_keeps_the_discount():
    d = decide(tr(700_000, payee_type="legal", payee_company_age_days=2000), cust(), Events(), [], V2)
    assert "S9" in codes(d) and "S14" not in codes(d)


def test_unknown_company_age_gets_no_discount_under_v2():
    d = decide(tr(700_000, payee_type="legal"), cust(), Events(), [], V2)
    assert "S9" not in codes(d) and "S14" not in codes(d)


# ---- v1 is untouched -------------------------------------------------------
def test_v1_rules_ignore_the_new_signals_and_keep_the_old_discount():
    d = decide(tr(2_200_000, payee_type="legal", payee_company_age_days=40), cust(week=3_000_000),
               LOAN, _days(5, 400_000), V1)
    assert not codes(d) & {"S12", "S13", "S14"}
    assert "S9" in codes(d)
