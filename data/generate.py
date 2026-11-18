"""Synthetic scenario generator. EVERYTHING here is invented by the team.

Two sets, two seeds:
  tune    seed 42,   nominal parameters           (used to tune thresholds)
  holdout seed 2026, amounts x(0.7..1.3), intervals x(0.5..1.5) per scenario
                    (frozen by SHA-256, measured once)

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


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + TZ


def _round(x: float, step: int = 1000) -> int:
    return max(step, int(round(x / step)) * step)


class Gen:
    def __init__(self, seed: int, shifted: bool):
        self.r = random.Random(seed)
        self.shifted = shifted
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


def build(g: Gen, typ: str, idx: int, split: str) -> dict:
    label, hard, evasion, _, _ = TYPES[typ]
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


def make_set(split: str) -> list[dict]:
    seed, shifted, col = (42, False, 3) if split == "tune" else (2026, True, 4)
    g = Gen(seed, shifted)
    out = []
    for typ, spec in TYPES.items():
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
    main()
