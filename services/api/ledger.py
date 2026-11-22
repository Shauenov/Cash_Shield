"""Ledger: what the decision lifecycle needs to know about customers and money.

Two adapters satisfy the same interface:
* InMemoryLedger for tests and offline evaluation;
* SqliteLedger for the API (the demo database).

Unknown customer: `balance()` raises KeyError. Unknown decision: `get_decision()` returns None.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

TZ = timezone(timedelta(hours=5))

from engine import Events
from engine.signals import Executed


@dataclass
class _Customer:
    balance: int
    median_withdrawal: int
    events: Events
    history: list = field(default_factory=list)


class InMemoryLedger:
    def __init__(self) -> None:
        self._c: dict[str, _Customer] = {}
        self._d: dict[str, dict] = {}

    # decisions: plain dicts with decision_id, operation_id, customer_id, channel, type,
    # amount, ts, decision, score, reasons, status, pause_until
    def save_decision(self, rec: dict) -> None:
        self._d[rec["decision_id"]] = dict(rec)

    def get_decision(self, did: str) -> Optional[dict]:
        rec = self._d.get(did)
        return dict(rec) if rec else None

    def update_decision(self, did: str, **fields) -> None:
        self._d[did].update(fields)

    def add_customer(self, cid: str, balance: int, median_withdrawal: int,
                     loan_issued_at: Optional[datetime] = None,
                     deposit_closed_at: Optional[datetime] = None,
                     report_at: Optional[datetime] = None) -> None:
        self._c[cid] = _Customer(balance, median_withdrawal,
                                 Events(loan_issued_at, deposit_closed_at, report_at))

    def balance(self, cid: str) -> int:
        return self._c[cid].balance

    def median_withdrawal(self, cid: str) -> int:
        return self._c[cid].median_withdrawal

    def events(self, cid: str) -> Events:
        return self._c[cid].events

    def history(self, cid: str) -> list[Executed]:
        return list(self._c[cid].history)

    def execute(self, cid: str, ts: datetime, typ: str, amount: int, asked: bool) -> None:
        c = self._c[cid]
        c.history.append(Executed(ts, typ, amount, asked))
        c.balance -= amount


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=TZ)


class SqliteLedger:
    """The demo database (tables created by services/api/main.py). All calls take the shared lock."""

    def __init__(self, db, lock) -> None:
        self.db, self.lock = db, lock

    def _customer(self, cid: str):
        with self.lock:
            row = self.db.execute("SELECT * FROM customers WHERE customer_id=?", (cid,)).fetchone()
        if row is None:
            raise KeyError(cid)
        return row

    def balance(self, cid: str) -> int:
        return self._customer(cid)["balance"]

    def median_withdrawal(self, cid: str) -> int:
        return self._customer(cid)["median_withdrawal"]

    def events(self, cid: str) -> Events:
        c = self._customer(cid)
        return Events(_dt(c["loan_issued_at"]), _dt(c["deposit_closed_at"]), _dt(c["report_at"]))

    def history(self, cid: str) -> list[Executed]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM history WHERE customer_id=? ORDER BY id", (cid,)).fetchall()
        return [Executed(_dt(h["ts"]), h["type"], h["amount"], bool(h["asked"])) for h in rows]

    def execute(self, cid: str, ts: datetime, typ: str, amount: int, asked: bool) -> None:
        with self.lock:
            self.db.execute("INSERT INTO history(customer_id,ts,type,amount,asked) VALUES (?,?,?,?,?)",
                            (cid, _iso(ts), typ, amount, int(asked)))
            self.db.execute("UPDATE customers SET balance=balance-? WHERE customer_id=?", (amount, cid))
            self.db.commit()

    _COLS = ("decision_id", "operation_id", "customer_id", "channel", "type", "amount", "ts", "decision",
             "score", "reasons", "status", "pause_until", "payee_id", "payee_type", "payee_known")

    def save_decision(self, rec: dict) -> None:
        r = dict(rec, ts=_iso(rec["ts"]), pause_until=_iso(rec.get("pause_until")),
                 reasons=json.dumps(rec["reasons"], ensure_ascii=False), payee_known=int(bool(rec.get("payee_known"))))
        with self.lock:
            self.db.execute(f"INSERT INTO decisions({','.join(self._COLS)}) VALUES ({','.join('?' * len(self._COLS))})",
                            tuple(r.get(c) for c in self._COLS))
            self.db.commit()

    def get_decision(self, did: str) -> Optional[dict]:
        with self.lock:
            row = self.db.execute("SELECT * FROM decisions WHERE decision_id=?", (did,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d.update(ts=_dt(d["ts"]), pause_until=_dt(d["pause_until"]), reasons=json.loads(d["reasons"]),
                 payee_known=bool(d["payee_known"]))
        return d

    def update_decision(self, did: str, **fields) -> None:
        if "pause_until" in fields:
            fields["pause_until"] = _iso(fields["pause_until"])
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.lock:
            self.db.execute(f"UPDATE decisions SET {sets} WHERE decision_id=?", (*fields.values(), did))
            self.db.commit()

    def held_ids(self) -> list[str]:
        with self.lock:
            return [r["decision_id"] for r in self.db.execute("SELECT decision_id FROM decisions WHERE status='held'")]
