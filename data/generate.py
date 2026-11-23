"""Synthetic scenario generator. EVERYTHING here is invented by the team.

Two sets, two seeds:
  tune    seed 42,   nominal parameters           (used to tune thresholds)
  holdout seed 2026, amounts x(0.7..1.3), intervals x(0.5..1.5) per scenario
                    (frozen by SHA-256, measured once)

Version 2 sets (added 2026-11-23, after the red team found four bypasses):
  tune2    seed 4242, nominal parameters
  holdout2 seed 7171, shifted like the holdout (frozen by SHA-256 in HOLDOUT2.sha256
           BEFORE any v2 rule was written, measured once for v1 and once for v2)
  They hold every v1 type plus TYPES_V2: the red-team attacks and honest look-alikes.
  Their operations carry `payee_company_age_days` (days since the recipient company
  was registered; the bank can read it from the state register). The v1 sets are
  generated exactly as before, byte for byte. Run: python data/generate.py --v2

Outputs (JSONL, one scenario per line) go next to this file.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
BASE = datetime(2026, 11, 10, 9, 0)
TZ = "+05:00"
ATM_LIMIT = 500_000   # per-operation ATM limit (ASSUMPTION, verify with mentor)

# type -> (label, hard, evasion, tune_count, holdout_count)
TYPES = {
    "small_withdrawal":      ("normal", False, False, 54, 36),
    "salary_day":            ("normal", False, False, 24, 16),
    "known_transfer":        ("normal", False, False, 30, 20),
    "pensioner_all":         ("normal", True,  False, 18, 12),
    "planned_purchase":      ("normal", True,  False, 18, 12),
    "contractor_new_payee":  ("normal", True,  False, 18, 12),
    "loan_honest_spend":     ("normal", True,  False, 12, 8),
    "phone_call_at_atm":     ("normal", True,  False, 6, 4),
    "loan_then_atm_series":  ("fraud",  False, False, 21, 14),
    "loan_then_cash_desk":   ("fraud",  False, False, 15, 10),
    "deposit_close_transfer":("fraud",  False, False, 21, 14),
    "savings_no_loan":       ("fraud",  False, False, 12, 8),
    "split_below_limit":     ("fraud",  False, True,  9, 6),
    "headset":               ("fraud",  False, True,  6, 4),
    "video_call":            ("fraud",  False, True,  6, 4),
}

# v2 only: red-team bypasses and honest look-alikes (same tuple layout as TYPES)
TYPES_V2 = {
    "family_large_transfer": ("normal", True,  False, 12, 8),
    "weekly_spending":       ("normal", True,  False, 18, 12),
    "loan_transfer_known":   ("fraud",  False, False, 12, 8),
    "loan_transfer_company": ("fraud",  False, False, 15, 10),
    "slow_drip_days":        ("fraud",  False, True,  12, 8),
}
COMPANY_FRAUD = {"loan_transfer_company"}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + TZ


def _round(x: float, step: int = 1000) -> int:
    return max(step, int(round(x / step)) * step)


class Gen:
    def __init__(self, seed: int, shifted: bool, v2: bool = False):
        self.r = random.Random(seed)
        self.shifted = shifted
        self.v2 = v2
        self.n = 0

    # shifted sets perturb amounts and time gaps
    def a(self) -> float:
        return self.r.uniform(0.7, 1.3) if self.shifted else 1.0

    def t(self) -> float:
        return self.r.uniform(0.5, 1.5) if self.shifted else 1.0

    def start(self) -> datetime:
        d = self.r.randint(0, 20)
        return BASE + timedelta(days=d, hours=self.r.uniform(0, 9))

    def age(self, lo=22, hi=78) -> int:
        return self.r.randint(lo, hi)

    def median_w(self, am: float) -> int:
        return _round(self.r.lognormvariate(10.3, 0.35) * am, 1000)  # median ~30k

    def op(self, ts, channel, typ, amount, payee_type=None, known=False,
           terminal=None, phone=None):
        self.n += 1
        return {
            "op_id": f"op_{self.n:06d}", "ts": _iso(ts), "channel": channel,
            "type": typ, "amount": int(amount),
            "payee_id": None if typ == "cash_withdrawal" else f"p_{self.r.randint(100, 999)}",
            "payee_type": payee_type, "payee_known": known,
            "terminal_id": terminal, "phone_at_ear_sec": phone,
        }

    def atm(self) -> str:
        return f"atm_{self.r.randint(1, 60):03d}"


def _loan(g, ev, t0, a, t):
    r = g.r
    loan = _round(r.uniform(1_500_000, 3_500_000) * a)
    ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 20) * t))
    return loan


def build(g: Gen, typ: str, idx: int, split: str) -> dict:
    label, hard, evasion, _, _ = {**TYPES, **TYPES_V2}[typ]
    r, a, t = g.r, g.a(), g.t()
    t0 = g.start()
    age = g.age()
    ev = {"loan_issued_at": None, "deposit_closed_early_at": None, "report_at": None}
    lies = False
    ops = []
    balance = 0
    median = g.median_w(a)

    if typ == "small_withdrawal":
        balance = _round(r.lognormvariate(12.9, 0.7) * a)
        amt = _round(r.uniform(5_000, 80_000) * a, 1000)
        ops.append(g.op(t0, "atm", "cash_withdrawal", min(amt, balance // 2 or amt), terminal=g.atm()))

    elif typ == "salary_day":
        balance = _round(r.uniform(250_000, 900_000) * a)
        amt = _round(balance * r.uniform(0.5, 0.9), 1000)
        ch = r.choice(["atm", "cash_desk"])
        ops.append(g.op(t0, ch, "cash_withdrawal", min(amt, ATM_LIMIT) if ch == "atm" else amt,
                        terminal=g.atm() if ch == "atm" else "desk_01"))

    elif typ == "known_transfer":
        balance = _round(r.lognormvariate(13.0, 0.6) * a)
        amt = _round(min(r.uniform(20_000, 400_000) * a, balance * 0.6))
        ops.append(g.op(t0, "app", "transfer", amt, payee_type="individual", known=True))

    elif typ == "pensioner_all":
        age = g.age(60, 80)
        balance = _round(r.uniform(100_000, 250_000) * a)
        ops.append(g.op(t0, "atm", "cash_withdrawal", balance, terminal=g.atm()))

    elif typ == "planned_purchase":
        balance = _round(r.uniform(1_500_000, 5_000_000) * a)
        amt = _round(r.uniform(300_000, 1_500_000) * a)
        if r.random() < 0.3:   # buy with two withdrawals the same day
            h = amt // 2
            ops.append(g.op(t0, "cash_desk", "cash_withdrawal", h, terminal="desk_01"))
            ops.append(g.op(t0 + timedelta(hours=r.uniform(0.5, 4) * t), "cash_desk",
                            "cash_withdrawal", amt - h, terminal="desk_01"))
        else:
            ops.append(g.op(t0, "cash_desk", "cash_withdrawal", amt, terminal="desk_01"))

    elif typ == "contractor_new_payee":
        balance = _round(r.uniform(800_000, 4_000_000) * a)
        amt = _round(r.uniform(200_000, 1_500_000) * a)
        ptype = r.choice(["individual", "legal"])
        ops.append(g.op(t0, "app", "transfer", min(amt, balance), payee_type=ptype, known=False))

    elif typ == "loan_honest_spend":
        loan = _round(r.uniform(1_000_000, 4_000_000) * a)
        balance = loan + _round(r.uniform(50_000, 600_000) * a)
        ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(1, 20) * t))
        kind = r.choice(["legal", "legal", "cash_small", "cash_large"])
        if kind == "legal":
            ops.append(g.op(t0, "app", "transfer", _round(loan * r.uniform(0.2, 0.9)),
                            payee_type="legal", known=False))
        elif kind == "cash_small":
            ops.append(g.op(t0, "atm", "cash_withdrawal", _round(r.uniform(50_000, 250_000) * a),
                            terminal=g.atm()))
        else:
            ops.append(g.op(t0, "cash_desk", "cash_withdrawal", _round(r.uniform(300_000, 800_000) * a),
                            terminal="desk_01"))

    elif typ == "phone_call_at_atm":
        balance = _round(r.lognormvariate(12.9, 0.6) * a)
        amt = _round(r.uniform(10_000, 120_000) * a)
        ops.append(g.op(t0, "atm", "cash_withdrawal", min(amt, balance // 2 or amt),
                        terminal=g.atm(), phone=round(r.uniform(4, 60), 1)))

    elif typ == "loan_then_atm_series":
        age = g.age(45, 78)
        loan = _round(r.uniform(1_500_000, 3_500_000) * a)
        balance = loan + _round(r.uniform(50_000, 500_000) * a)
        ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 20) * t))
        lies = r.random() < 0.7
        _series(g, ops, t0, r.randint(2, 6), (150_000, ATM_LIMIT), a, t, phone_p=0.7)

    elif typ == "loan_then_cash_desk":
        age = g.age(45, 78)
        loan = _round(r.uniform(1_500_000, 4_000_000) * a)
        balance = loan + _round(r.uniform(50_000, 400_000) * a)
        ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 20) * t))
        lies = r.random() < 0.7
        ops.append(g.op(t0, "cash_desk", "cash_withdrawal",
                        _round(loan * r.uniform(0.6, 1.0)), terminal="desk_01"))

    elif typ == "deposit_close_transfer":
        age = g.age(45, 78)
        balance = _round(r.uniform(600_000, 5_000_000) * a)
        ev["deposit_closed_early_at"] = _iso(t0 - timedelta(hours=r.uniform(0.2, 12) * t))
        lies = r.random() < 0.7
        ops.append(g.op(t0, "app", "transfer", _round(balance * r.uniform(0.5, 1.0)),
                        payee_type="individual", known=False))

    elif typ == "savings_no_loan":
        age = g.age(45, 78)
        balance = _round(r.uniform(1_000_000, 4_000_000) * a)
        lies = r.random() < 0.7
        if r.random() < 0.5:
            ops.append(g.op(t0, "cash_desk", "cash_withdrawal",
                            _round(balance * r.uniform(0.5, 0.95)), terminal="desk_01"))
        else:
            _series(g, ops, t0, r.randint(2, 4), (250_000, ATM_LIMIT), a, t, phone_p=0.7)

    elif typ == "split_below_limit":
        age = g.age(45, 78)
        loan = _round(r.uniform(1_500_000, 3_000_000) * a)
        balance = loan + _round(r.uniform(50_000, 400_000) * a)
        ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 20) * t))
        lies = r.random() < 0.7
        _series(g, ops, t0, r.randint(4, 7), (150_000, 290_000), a, t, phone_p=0.7)

    elif typ == "headset":
        age = g.age(45, 78)
        loan = _round(r.uniform(1_500_000, 3_500_000) * a)
        balance = loan + _round(r.uniform(50_000, 400_000) * a)
        ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 20) * t))
        lies = r.random() < 0.7
        _series(g, ops, t0, r.randint(2, 5), (150_000, ATM_LIMIT), a, t, phone_p=0.0)

    elif typ == "video_call":
        age = g.age(45, 78)
        loan = _round(r.uniform(1_500_000, 3_500_000) * a)
        balance = loan + _round(r.uniform(50_000, 400_000) * a)
        ev["loan_issued_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 20) * t))
        lies = r.random() < 0.7
        _series(g, ops, t0, r.randint(2, 5), (150_000, ATM_LIMIT), a, t, phone_p=0.0, video=True)

    elif typ == "family_large_transfer":
        # honest: a large sum to a known relative (a flat, a wedding); sometimes from a closed deposit
        balance = _round(r.uniform(800_000, 4_000_000) * a)
        if r.random() < 0.25:
            ev["deposit_closed_early_at"] = _iso(t0 - timedelta(hours=r.uniform(0.5, 12) * t))
        ops.append(g.op(t0, "app", "transfer", _round(balance * r.uniform(0.3, 0.85)),
                        payee_type="individual", known=True))

    elif typ == "weekly_spending":
        # honest: a renovation or a move, several payments over a week; sometimes after a loan
        balance = _round(r.uniform(1_000_000, 5_000_000) * a)
        if r.random() < 0.25:
            balance += _loan(g, ev, t0, a, t)
        n = r.randint(3, 6)
        total = balance * r.uniform(0.4, 0.9)
        ts = t0
        for _ in range(n):
            amt = _round(total / n * r.uniform(0.7, 1.3))
            if r.random() < 0.5:
                ops.append(g.op(ts, "cash_desk", "cash_withdrawal", amt, terminal="desk_01"))
            else:
                ops.append(g.op(ts, "app", "transfer", amt, payee_type="legal", known=r.random() < 0.3))
            ts = ts + timedelta(hours=r.uniform(10, 40) * t)

    elif typ == "loan_transfer_known":
        # red team 6: the victim sends the loan to a recipient she already knows
        age = g.age(45, 78)
        loan = _loan(g, ev, t0, a, t)
        balance = loan + _round(r.uniform(50_000, 400_000) * a)
        lies = r.random() < 0.7
        ops.append(g.op(t0, "app", "transfer", _round(loan * r.uniform(0.6, 0.95)),
                        payee_type="individual", known=True))

    elif typ == "loan_transfer_company":
        # red team 7 and 8: the loan goes to one to three companies (mostly fresh shells)
        age = g.age(45, 78)
        loan = _loan(g, ev, t0, a, t)
        balance = loan + _round(r.uniform(50_000, 400_000) * a)
        lies = r.random() < 0.7
        n = r.randint(1, 3)
        total = loan * r.uniform(0.6, 0.95)
        ts = t0
        for _ in range(n):
            ops.append(g.op(ts, "app", "transfer", _round(total / n), payee_type="legal", known=False))
            ts = ts + timedelta(minutes=r.uniform(10, 90) * t)

    elif typ == "slow_drip_days":
        # red team 10: one modest operation a day for several days, under every 24 h window
        age = g.age(45, 78)
        balance = _round(r.uniform(1_500_000, 4_000_000) * a)
        if r.random() < 0.5:
            balance += _loan(g, ev, t0, a, t)
        lies = r.random() < 0.7
        days = r.randint(4, 7)
        per = balance * r.uniform(0.6, 0.95) / days
        ts = t0
        for _ in range(days):
            amt = _round(per * r.uniform(0.85, 1.15))
            if amt <= ATM_LIMIT and r.random() < 0.7:
                ops.append(g.op(ts, "atm", "cash_withdrawal", amt, terminal=g.atm(),
                                phone=round(r.uniform(0, 30), 1)))
            else:
                ops.append(g.op(ts, "cash_desk", "cash_withdrawal", amt, terminal="desk_01"))
            ts = ts + timedelta(hours=r.uniform(23, 30) * t)

    if g.v2:
        # days since the recipient company was registered (None for people and cash)
        for o in ops:
            if o["payee_type"] == "legal":
                p_new = 0.75 if typ in COMPANY_FRAUD else 0.12
                o["payee_company_age_days"] = (r.randint(5, 170) if r.random() < p_new
                                               else r.randint(400, 6000))
            else:
                o["payee_company_age_days"] = None

    # button press ("scammer on the line"): ASSUMPTION ~15% of fraud, ~1% of normal
    p_report = 0.15 if label == "fraud" else 0.01
    if r.random() < p_report:
        ev["report_at"] = _iso(t0 - timedelta(hours=r.uniform(0.1, 6) * t))

    ops.sort(key=lambda o: o["ts"])
    return {
        "id": f"{split}_{typ}_{idx:03d}", "split": split, "type": typ, "label": label,
        "hard": hard, "evasion": evasion, "lies_on_question": lies,
        "age": age, "age_group": "18-34" if age < 35 else ("35-54" if age < 55 else "55+"),
        "customer": {"customer_id": f"c_{r.randint(1, 500):04d}",
                     "balance_24h_start": int(balance), "median_withdrawal": int(median)},
        "events": ev, "operations": ops,
    }


def _series(g, ops, t0, n, amt_range, a, t, phone_p, video=False):
    r = g.r
    ts = t0
    for _ in range(n):
        amt = min(_round(r.uniform(*amt_range) * a), ATM_LIMIT)
        if not video and phone_p and r.random() < phone_p:
            phone = round(r.uniform(4, 40), 1)      # phone at the ear
        else:
            phone = round(r.uniform(0, 2), 1)       # headset / video call / speaker: camera sees no phone at the ear
        ops.append(g.op(ts, "atm", "cash_withdrawal", amt, terminal=g.atm(), phone=phone))
        ts = ts + timedelta(minutes=r.uniform(8, 50) * t)


SETS = {  # split -> (seed, shifted, count column, v2)
    "tune": (42, False, 3, False), "holdout": (2026, True, 4, False),
    "tune2": (4242, False, 3, True), "holdout2": (7171, True, 4, True),
}


def make_set(split: str) -> list[dict]:
    seed, shifted, col, v2 = SETS[split]
    g = Gen(seed, shifted, v2)
    out = []
    for typ, spec in ({**TYPES, **TYPES_V2} if v2 else TYPES).items():
        for i in range(spec[col]):
            out.append(build(g, typ, i, split))
    g.r.shuffle(out)
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_customers(rows_tune: list[dict]) -> None:
    """customers.csv: unique customer snapshots, used by the demo database."""
    seen = {}
    for s in rows_tune:
        c = s["customer"]
        seen.setdefault(c["customer_id"], (c["balance_24h_start"], c["median_withdrawal"], s["age"]))
    with open(HERE / "customers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["customer_id", "balance", "median_withdrawal", "age"])
        for cid, (b, m, age) in sorted(seen.items()):
            w.writerow([cid, b, m, age])


def main_v2() -> None:
    """v2 sets. holdout2 is written once; a frozen one is only checked, never overwritten."""
    tune = make_set("tune2")
    write_jsonl(HERE / "scenarios_tune2.jsonl", tune)
    print(f"tune2: {len(tune)} scenarios")
    path, lock = HERE / "scenarios_holdout2.jsonl", HERE / "HOLDOUT2.sha256"
    hold = make_set("holdout2")
    if lock.exists():
        tmp = HERE / "_holdout2_check.jsonl"
        write_jsonl(tmp, hold)
        same = sha256(tmp) == lock.read_text().strip()
        tmp.unlink()
        print("holdout2: frozen; regenerated bytes " + ("match" if same else "DO NOT MATCH") + " the lock")
        return
    write_jsonl(path, hold)
    lock.write_text(sha256(path) + "\n", encoding="utf-8")
    print(f"holdout2: {len(hold)} scenarios, sha256 {sha256(path)[:16]}... (frozen)")


def main(include_holdout: bool = True) -> None:
    tune = make_set("tune")
    write_jsonl(HERE / "scenarios_tune.jsonl", tune)
    write_customers(tune)
    print(f"tune: {len(tune)} scenarios")
    if include_holdout:
        hold = make_set("holdout")
        path = HERE / "scenarios_holdout.jsonl"
        write_jsonl(path, hold)
        (HERE / "HOLDOUT.sha256").write_text(sha256(path) + "\n", encoding="utf-8")
        print(f"holdout: {len(hold)} scenarios, sha256 {sha256(path)[:16]}...")


if __name__ == "__main__":
    import sys
    main_v2() if "--v2" in sys.argv else main()
