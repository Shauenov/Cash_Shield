"""Signals S1-S14 (S12-S14: v2 only). Pure functions: no I/O, no web dependencies.

Every signal returns None (did not fire) or (code, text_ru, text_en, text_kz). The weight
comes from rules.yaml, so the engine can be re-tuned without code changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class Operation:
    op_id: str
    ts: datetime
    channel: str            # atm | cash_desk | app
    type: str               # cash_withdrawal | transfer
    amount: int             # KZT
    payee_id: Optional[str] = None
    payee_type: Optional[str] = None   # individual | legal | None
    payee_known: bool = False
    terminal_id: Optional[str] = None
    phone_at_ear_sec: Optional[float] = None
    payee_company_age_days: Optional[int] = None   # v2: days since the recipient company was registered
    camera_blocked: bool = False   # S15: the ATM camera saw a covered or blacked-out lens during the operation


@dataclass
class Customer:
    customer_id: str
    balance_24h_start: int   # balance at the start of the 24h window
    median_withdrawal: int   # median cash withdrawal over the last 180 days
    balance_7d_start: Optional[int] = None   # v2: balance at the start of the 7-day window


@dataclass
class Events:
    loan_issued_at: Optional[datetime] = None
    deposit_closed_early_at: Optional[datetime] = None
    report_at: Optional[datetime] = None


@dataclass
class Executed:
    """A past operation that actually went through (counts toward 24h sums)."""
    ts: datetime
    type: str
    amount: int
    asked: bool = False   # the customer was asked the question and answered "no"


Hit = Optional[tuple]


def _within(ts: Optional[datetime], now: datetime, hours: float) -> bool:
    return ts is not None and timedelta(0) <= now - ts < timedelta(hours=hours)


def _window(history: list[Executed], now: datetime, hours: float) -> list[Executed]:
    return [h for h in history if timedelta(0) <= now - h.ts < timedelta(hours=hours)]


def s1_loan_recent(op, cust, ev, hist, p) -> Hit:
    if _within(ev.loan_issued_at, op.ts, p["window_hours"]):
        hours = (op.ts - ev.loan_issued_at).total_seconds() / 3600
        return ("S1", f"Кредит выдан {hours:.0f} ч назад", f"Loan issued {hours:.0f} h ago",
                f"Несие {hours:.0f} сағ бұрын берілді")
    return None


def s2_balance_drain(op, cust, ev, hist, p) -> Hit:
    if cust.balance_24h_start <= 0:
        return None
    past = _window(hist, op.ts, p["window_hours"])
    total = sum(h.amount for h in past) + op.amount
    if total >= p["balance_share_min"] * cust.balance_24h_start:
        share = total / cust.balance_24h_start
        return ("S2", f"За сутки выводится {share:.0%} остатка", f"{share:.0%} of the balance moved out within 24 h",
                f"Тәулік ішінде қалдықтың {share:.0%} шығарылды")
    return None


def s3_large_cash(op, cust, ev, hist, p) -> Hit:
    if op.type != "cash_withdrawal":
        return None
    if op.amount >= p["cash_large_min_kzt"] and op.amount >= p["cash_large_median_mult"] * cust.median_withdrawal:
        return ("S3", "Необычно крупное снятие наличных", "Unusually large cash withdrawal",
                "Әдеттен тыс ірі қолма-қол ақша шешу")
    return None


def s4_series(op, cust, ev, hist, p) -> Hit:
    if op.type != "cash_withdrawal":
        return None
    past = [h for h in _window(hist, op.ts, p["window_hours"]) if h.type == "cash_withdrawal"]
    n = len(past) + 1
    total = sum(h.amount for h in past) + op.amount
    if n >= p["series_min_ops"] and total >= p["series_min_total_kzt"]:
        tot = f"{total:,}".replace(",", " ")
        return ("S4", f"Серия снятий за сутки: {n} шт., всего {tot} ₸", f"Series of {n} withdrawals within 24 h, {tot} ₸ total",
                f"Тәулік ішінде {n} рет ақша шешілді, барлығы {tot} ₸")
    return None


def s5_new_payee(op, cust, ev, hist, p) -> Hit:
    if op.type == "transfer" and not op.payee_known and op.amount >= p["new_payee_min_kzt"]:
        return ("S5", "Перевод новому получателю", "Transfer to a new recipient",
                "Жаңа алушыға аударым")
    return None


def s6_deposit_closed(op, cust, ev, hist, p) -> Hit:
    if _within(ev.deposit_closed_early_at, op.ts, p["window_hours"]):
        return ("S6", "Депозит закрыт досрочно менее суток назад", "Deposit closed early less than 24 h ago",
                "Депозит бір тәуліктен аз уақыт бұрын мерзімінен бұрын жабылды")
    return None


def s11_escalation(op, cust, ev, hist, p) -> Hit:
    """The customer already answered 'no' to the question and is now trying again.

    A coached victim learns to answer 'no'. A second risky attempt right after
    that is stronger evidence than the first one, and it does not depend on
    what the customer says.
    """
    win = p.get("escalation_window_hours", p["window_hours"])
    if any(h.asked for h in _window(hist, op.ts, win)):
        return ("S11", "После вопроса клиент пробует снять или перевести ещё раз", "Customer answered the question, then tries again",
                "Сұрақтан кейін клиент қайтадан ақша шешуге немесе аударуға тырысуда")
    return None


def s8_report(op, cust, ev, hist, p) -> Hit:
    if _within(ev.report_at, op.ts, p["window_hours"]):
        return ("S8", "Клиент сообщил, что ему звонит мошенник", "Customer reported a scammer on the line",
                "Клиент өзіне алаяқ қоңырау шалып жатқанын хабарлады")
    return None


def s9_legal_payee(op, cust, ev, hist, p) -> Hit:
    if op.type == "transfer" and op.payee_type == "legal":
        min_age = p.get("legal_discount_min_age_days")   # v2 only; v1 discounts every company
        if min_age is not None and (op.payee_company_age_days is None or op.payee_company_age_days < min_age):
            return None
        return ("S9", "Получатель — юридическое лицо", "Recipient is a company",
                "Алушы — заңды тұлға")
    return None


# ---- v2 signals: run only when the rules give them a weight ----------------
def s12_loan_money_out(op, cust, ev, hist, p) -> Hit:
    """Money from a fresh loan or a closed deposit leaves by transfer, to anyone."""
    if op.type != "transfer" or cust.balance_24h_start <= 0:
        return None
    if not (_within(ev.loan_issued_at, op.ts, p["window_hours"])
            or _within(ev.deposit_closed_early_at, op.ts, p["window_hours"])):
        return None
    total = sum(h.amount for h in _window(hist, op.ts, p["window_hours"]) if h.type == "transfer") + op.amount
    if total >= p["s12_share"] * cust.balance_24h_start:
        share = total / cust.balance_24h_start
        return ("S12", f"Деньги кредита или вклада уходят переводом: {share:.0%} остатка",
                f"Loan or deposit money leaves by transfer: {share:.0%} of the balance",
                f"Несие немесе салым ақшасы аударыммен кетуде: қалдықтың {share:.0%}")
    return None


def s13_week_drain(op, cust, ev, hist, p) -> Hit:
    """Most of the balance leaves over several days, below every 24-hour check."""
    if not cust.balance_7d_start:
        return None
    past = _window(hist, op.ts, p["week_hours"])
    if not any(op.ts - h.ts >= timedelta(hours=p["window_hours"]) for h in past):
        return None   # all within one day: S2 and S4 cover that
    total = sum(h.amount for h in past) + op.amount
    if total >= p["s13_share"] * cust.balance_7d_start and total >= p["s13_min_kzt"]:
        share = total / cust.balance_7d_start
        return ("S13", f"За 7 дней выведено {share:.0%} остатка", f"{share:.0%} of the balance moved out over 7 days",
                f"7 күнде қалдықтың {share:.0%} шығарылды")
    return None


def s14_young_company(op, cust, ev, hist, p) -> Hit:
    age = op.payee_company_age_days
    if op.type == "transfer" and op.payee_type == "legal" and age is not None and age < p["s14_max_age_days"]:
        return ("S14", f"Компания-получатель зарегистрирована {age} дн. назад",
                f"Recipient company registered {age} days ago",
                f"Алушы компания {age} күн бұрын тіркелген")
    return None


def s15_camera_blocked(op, cust, ev, hist, p) -> Hit:
    """The ATM camera was covered during the operation. Honest customers almost never do this;
    a coached victim may be told to, so the phone at the ear is not seen. Runs only when the rules
    give S15 a weight (added 2026-11-25, weight set by reasoning, not tuned: no scenario has it)."""
    if op.camera_blocked:
        return ("S15", "Камера банкомата была закрыта во время операции", "ATM camera was covered during the operation",
                "Операция кезінде банкомат камерасы жабылды")
    return None


def s10_phone_at_ear(op, cust, ev, hist, p) -> Hit:
    sec = op.phone_at_ear_sec
    if sec is not None and sec > p["phone_at_ear_min_sec"]:
        return ("S10", "Камера: телефон у уха", "Camera: phone at the ear",
                "Камера: телефон құлақта")
    return None
