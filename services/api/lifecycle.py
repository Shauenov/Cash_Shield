"""Decision lifecycle: what happens to an operation from submit to money moving (or not).

One module for the API and for offline evaluation, so the metrics measure the same
code the demo runs. Time comes from a Clock, customers, money and decisions from a
Ledger. Every transition is reported to `events(kind, rec, actor, comment)`; every
pause or hold is passed to `notify(rec)` (the trusted-person message, if consented).
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from engine import Customer, Operation, decide, load_rules


class Conflict(Exception):
    """The decision is not in a state that allows this step (or the money is no longer there)."""


class NotFound(Exception):
    """No such decision."""


@dataclass(frozen=True)
class OpRequest:
    operation_id: str
    customer_id: str
    channel: str            # atm | cash_desk | app
    type: str               # cash_withdrawal | transfer
    amount: int
    payee_id: Optional[str] = None
    payee_type: Optional[str] = None
    payee_known: bool = False
    terminal_id: Optional[str] = None
    phone_at_ear_sec: Optional[float] = None


@dataclass
class Outcome:
    result: str             # approve | ask | hold | decline
    decision: str           # allow | ask | pause | hold | insufficient_funds
    score: Optional[int] = None
    reasons: list = field(default_factory=list)
    decision_id: Optional[str] = None
    pause_until: Optional[datetime] = None
    pause_seconds_left: Optional[int] = None
    engine_available: bool = True


def _quiet(*_args) -> None:
    return None


_POOL = ThreadPoolExecutor(max_workers=4)


class Lifecycle:
    def __init__(self, ledger, clock, rules: Optional[dict] = None, pause_minutes: int = 30,
                 events: Callable = _quiet, notify: Callable = _quiet,
                 engine: Optional[Callable] = None, timeout: float = 0.5) -> None:
        self.ledger, self.clock = ledger, clock
        self.rules = rules or load_rules()
        self.pause = timedelta(minutes=pause_minutes)
        self.events, self.notify = events, notify
        # the engine is a pure function of (operation, customer, events, history); swap it to test faults
        self.engine = engine or (lambda op, cust, ev, hist: decide(op, cust, ev, hist, self.rules))
        self.timeout = timeout

    # ------------------------------------------------------------ reading
    def _left(self, until: Optional[datetime]) -> Optional[int]:
        return None if until is None else max(0, int((until - self.clock.now()).total_seconds()))

    def current(self, did: str) -> dict:
        """The decision as of now: a pause past its end becomes `expired` (nothing moves).
        A hold has no end and waits for an officer."""
        rec = self.ledger.get_decision(did)
        if rec is None:
            raise NotFound(did)
        if (rec["status"] == "held" and rec["decision"] == "pause"
                and rec["pause_until"] is not None and rec["pause_until"] <= self.clock.now()):
            self.ledger.update_decision(did, status="expired")
            rec["status"] = "expired"
            self.events("pause_expired", rec, "engine", "pause ended: operation cancelled, nothing moved")
        return rec

    def status(self, did: str) -> str:
        return self.current(did)["status"]

    def _outcome(self, result: str, rec: dict) -> Outcome:
        return Outcome(result, rec["decision"], rec["score"], rec["reasons"], rec["decision_id"],
                       rec["pause_until"], self._left(rec["pause_until"]))

    # ------------------------------------------------------------ steps
    def submit(self, req: OpRequest) -> Outcome:
        ts = self.clock.now().replace(microsecond=0)   # stored with second precision
        cid = req.customer_id
        if req.amount > self.ledger.balance(cid):
            rec = dict(decision_id=None, operation_id=req.operation_id, customer_id=cid,
                       channel=req.channel, decision="insufficient_funds", score=None, reasons=[])
            self.events("insufficient_funds", rec, "host", f"amount {req.amount} above balance")
            return Outcome("decline", "insufficient_funds")
        hist = self.ledger.history(cid)
        window = [h for h in hist if timedelta(0) <= ts - h.ts < timedelta(hours=24)]
        cust = Customer(cid, self.ledger.balance(cid) + sum(h.amount for h in window),
                        self.ledger.median_withdrawal(cid))
        op = Operation(req.operation_id, ts, req.channel, req.type, req.amount, req.payee_id,
                       req.payee_type, req.payee_known, req.terminal_id, req.phone_at_ear_sec)
        try:
            res = _POOL.submit(self.engine, op, cust, self.ledger.events(cid), hist).result(timeout=self.timeout)
            if res is None:
                raise RuntimeError("engine returned nothing")
        except Exception:   # timeout or crash: fail-open, a fault in our module never blocks cash
            rec = dict(decision_id=f"d_{uuid.uuid4().hex[:8]}", operation_id=req.operation_id,
                       customer_id=cid, channel=req.channel, decision="allow", score=0, reasons=[])
            self.events("engine_unavailable", rec, "engine", "host approved: fail-open policy")
            self.ledger.execute(cid, ts, req.type, req.amount, False)
            return Outcome("approve", "allow", 0, [], rec["decision_id"], engine_available=False)
        rec = dict(decision_id=f"d_{uuid.uuid4().hex[:8]}", operation_id=req.operation_id,
                   customer_id=cid, channel=req.channel, type=req.type, amount=req.amount, ts=ts,
                   decision=res.decision, score=res.score, reasons=res.reasons,
                   payee_id=req.payee_id, payee_type=req.payee_type, payee_known=req.payee_known,
                   status={"allow": "approved", "ask": "open"}.get(res.decision, "held"),
                   pause_until=ts + self.pause if res.decision == "pause" else None)
        self.ledger.save_decision(rec)
        self.events("decision", rec, "engine", "")
        if res.decision == "allow":
            self.ledger.execute(cid, ts, req.type, req.amount, False)
            return self._outcome("approve", rec)
        if res.decision == "ask":
            return self._outcome("ask", rec)
        self.notify(rec)
        return self._outcome("hold", rec)

    def answer(self, did: str, yes: bool) -> Outcome:
        rec = self.current(did)
        if rec["status"] != "open":
            raise Conflict("decision already closed")
        if yes:
            until = rec["ts"] + self.pause
            self.ledger.update_decision(did, status="held", decision="pause", pause_until=until)
            rec.update(status="held", decision="pause", pause_until=until)
            self.events("answer", rec, "customer", "yes: they are asking me by phone")
            self.notify(rec)
            return self._outcome("hold", rec)
        if rec["amount"] > self.ledger.balance(rec["customer_id"]):
            raise Conflict("insufficient funds")
        self.ledger.update_decision(did, status="approved")
        self.ledger.execute(rec["customer_id"], rec["ts"], rec["type"], rec["amount"], True)
        self.events("answer", rec, "customer", "no: my own decision")
        return self._outcome("approve", rec)

    def release(self, did: str, officer: str, comment: str) -> Outcome:
        """An officer lets a paused or held operation through (a false alarm)."""
        rec = self.current(did)
        if rec["status"] != "held":
            raise Conflict("decision is not on hold")
        if rec["amount"] > self.ledger.balance(rec["customer_id"]):
            raise Conflict("insufficient funds: the balance changed while on hold")
        self.ledger.update_decision(did, status="approved")
        self.ledger.execute(rec["customer_id"], rec["ts"], rec["type"], rec["amount"], False)
        self.events("override", rec, f"officer:{officer}", f"release (false alarm): {comment}")
        return self._outcome("approve", rec)

    def confirm_fraud(self, did: str, officer: str, comment: str) -> Outcome:
        """An officer confirms the customer was being coached: the operation is cancelled."""
        rec = self.current(did)
        if rec["status"] != "held":
            raise Conflict("decision is not on hold")
        self.ledger.update_decision(did, status="declined")
        self.events("override", rec, f"officer:{officer}", f"confirm_fraud: {comment}")
        return self._outcome("decline", rec)
