"""Cash Shield API + mock authorization host (one FastAPI app for the MVP).

Run:  python -m uvicorn services.api.main:app --port 8000
Only the host decision can stop a withdrawal: the screens never talk to the
engine directly. If the engine is silent for ENGINE_TIMEOUT_MS the host
approves and logs `engine_unavailable` (fail-open policy).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Without Docker nobody loads .env, so read it here. Real environment variables win.
if (ROOT / ".env").exists():
    for _line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from engine import Customer, Events, Operation, decide, load_rules  # noqa: E402
from engine.signals import Executed  # noqa: E402

TZ = timezone(timedelta(hours=5))
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "change-me")
ENGINE_TIMEOUT = float(os.getenv("ENGINE_TIMEOUT_MS", "500")) / 1000
PAUSE_MINUTES = int(os.getenv("PAUSE_MINUTES", "30"))
DB_PATH = os.getenv("DB_PATH", ":memory:")
RULES_PATH = os.getenv("RULES_PATH")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_DEMO_CHAT_ID", "")
# Demo-only endpoints (reset, time skip, engine outage switch) exist only when DEMO_MODE=1.
DEMO_MODE = os.getenv("DEMO_MODE") == "1"
# The host stamps the operation time. Only offline simulations (eval/redteam.py) may pass their own.
ALLOW_CLIENT_TIMESTAMP = os.getenv("ALLOW_CLIENT_TIMESTAMP") == "1"

RULES = load_rules(Path(RULES_PATH) if RULES_PATH else None)
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=4)
FORCE_ENGINE_DOWN = {"on": os.getenv("ENGINE_FORCE_DOWN") == "1"}  # test/demo switch

app = FastAPI(title="Cash Shield", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB = sqlite3.connect(DB_PATH, check_same_thread=False)
DB.row_factory = sqlite3.Row
WS_CLIENTS: set[WebSocket] = set()
LOOP: Optional[asyncio.AbstractEventLoop] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers(customer_id TEXT PRIMARY KEY, name TEXT, age INT, balance INT,
  median_withdrawal INT, loan_issued_at TEXT, deposit_closed_at TEXT, report_at TEXT);
CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, ts TEXT,
  type TEXT, amount INT, asked INT);
CREATE TABLE IF NOT EXISTS decisions(decision_id TEXT PRIMARY KEY, operation_id TEXT, customer_id TEXT,
  channel TEXT, type TEXT, amount INT, ts TEXT, decision TEXT, score INT, reasons TEXT, status TEXT,
  pause_until TEXT, payee_id TEXT, payee_type TEXT, payee_known INT);
CREATE TABLE IF NOT EXISTS events(event_id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT,
  decision_id TEXT, customer_id TEXT, channel TEXT, score INT, decision TEXT, reasons TEXT,
  actor TEXT, comment TEXT);
CREATE TABLE IF NOT EXISTS consents(consent_id TEXT PRIMARY KEY, customer_id TEXT, contact_name TEXT,
  contact_chat TEXT, created_at TEXT, revoke_effective_at TEXT);
CREATE TABLE IF NOT EXISTS idem(key TEXT PRIMARY KEY, body_hash TEXT, response TEXT, created_at TEXT);
"""


def now() -> datetime:
    return datetime.now(TZ)


def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def parse(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=TZ)


# --------------------------------------------------------------------- seed
def seed() -> None:
    with LOCK:
        DB.executescript(SCHEMA)
        for t in ("customers", "history", "decisions", "events", "consents", "idem"):
            DB.execute(f"DELETE FROM {t}")
        n = now()
        rows = [
            ("c_gulnar", "Gulnar apa", 58, 3_000_000, 30_000, iso(n - timedelta(hours=3)), None, None),
            ("c_marat", "Marat (control)", 34, 800_000, 25_000, None, None, None),
            ("c_aigerim", "Aigerim", 61, 2_000_000, 20_000, None, iso(n - timedelta(hours=1)), None),
            ("c_serik", "Serik (buys a car)", 41, 3_200_000, 40_000, iso(n - timedelta(hours=2)), None, None),
            ("c_bolat", "Bolat (cash desk)", 66, 2_900_000, 30_000, iso(n - timedelta(hours=3)), None, None),
            ("c_dana", "Dana (consent on)", 29, 600_000, 28_000, None, None, None),
        ]
        DB.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", rows)
        DB.execute("INSERT INTO consents VALUES (?,?,?,?,?,NULL)",
                   ("k_seed", "c_gulnar", "Daughter Aliya", TELEGRAM_CHAT_ID, iso(n)))
        DB.commit()


seed()


# ------------------------------------------------------------------ helpers
def log_event(kind: str, d: Optional[dict] = None, actor: str = "engine", comment: str = "",
              customer_id: Optional[str] = None) -> dict:
    d = d or {}
    with LOCK:
        cur = DB.execute(
            "INSERT INTO events(ts,kind,decision_id,customer_id,channel,score,decision,reasons,actor,comment)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (iso(now()), kind, d.get("decision_id"), d.get("customer_id") or customer_id,
             d.get("channel"), d.get("score"), d.get("decision"),
             d.get("reasons") if isinstance(d.get("reasons"), str) else json.dumps(d.get("reasons") or [], ensure_ascii=False),
             actor, comment))
        DB.commit()
        row = dict(DB.execute("SELECT * FROM events WHERE event_id=?", (cur.lastrowid,)).fetchone())
    row["reasons"] = json.loads(row["reasons"] or "[]")
    row["event_id"] = f"e_{row['event_id']:06d}"
    if LOOP and WS_CLIENTS:
        asyncio.run_coroutine_threadsafe(_broadcast(row), LOOP)
    return row


async def _broadcast(row: dict) -> None:
    for ws in list(WS_CLIENTS):
        try:
            await ws.send_json(row)
        except Exception:
            WS_CLIENTS.discard(ws)


@app.on_event("startup")
async def _startup() -> None:
    global LOOP
    LOOP = asyncio.get_running_loop()


def need_token(x_service_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_service_token, SERVICE_TOKEN):
        raise HTTPException(401, "bad or missing X-Service-Token")


def need_demo() -> None:
    if not DEMO_MODE:
        raise HTTPException(404, "not found")


# Every endpoint except /healthz needs the service token. The screens get it from the
# reverse proxy (nginx in Docker, Vite in development), which plays the bank's terminal network.
api = APIRouter(dependencies=[Depends(need_token)])


def customer_state(cid: str, at: datetime) -> tuple[Customer, Events, list[Executed], dict]:
    with LOCK:
        c = DB.execute("SELECT * FROM customers WHERE customer_id=?", (cid,)).fetchone()
        if not c:
            raise HTTPException(404, "customer not found")
        hist = [Executed(parse(h["ts"]), h["type"], h["amount"], bool(h["asked"]))
                for h in DB.execute("SELECT * FROM history WHERE customer_id=?", (cid,))]
    window = [h for h in hist if timedelta(0) <= at - h.ts < timedelta(hours=24)]
    start_balance = c["balance"] + sum(h.amount for h in window)
    ev = Events(parse(c["loan_issued_at"]), parse(c["deposit_closed_at"]), parse(c["report_at"]))
    return Customer(cid, start_balance, c["median_withdrawal"]), ev, hist, dict(c)


def run_engine(op, cust, ev, hist):
    if FORCE_ENGINE_DOWN["on"]:
        raise RuntimeError("engine forced down")
    return decide(op, cust, ev, hist, RULES)


def active_consent(cid: str, at: datetime):
    with LOCK:
        for r in DB.execute("SELECT * FROM consents WHERE customer_id=?", (cid,)):
            eff = parse(r["revoke_effective_at"])
            if eff is None or at < eff:     # revocation only works after 24h
                return dict(r)
    return None


def notify_trusted(d: dict) -> None:
    c = active_consent(d["customer_id"], now())
    if not c:
        log_event("notify_skipped_no_consent", d)
        return
    text = ("Your relative asked us to tell you: the bank paused their unusual operation. "
            "Call them now. / Жақыныңыз сізге хабарлауды сұраған: банк оның әдеттен тыс "
            "операциясын тоқтатты. Оған қазір қоңырау шалыңыз.")
    simulated = True
    if TELEGRAM_BOT_TOKEN and c.get("contact_chat"):
        try:
            import httpx
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                       json={"chat_id": c["contact_chat"], "text": text}, timeout=3)
            simulated = False
        except Exception:
            simulated = True
    log_event("notify_sent", d, comment=("simulated: " if simulated else "telegram: ") + c["contact_name"])


def apply_executed(cid: str, ts: datetime, typ: str, amount: int, asked: bool) -> None:
    with LOCK:
        DB.execute("INSERT INTO history(customer_id,ts,type,amount,asked) VALUES (?,?,?,?,?)",
                   (cid, iso(ts), typ, amount, int(asked)))
        DB.execute("UPDATE customers SET balance=balance-? WHERE customer_id=?", (amount, cid))
        DB.commit()


def balance_of(cid: str) -> int:
    with LOCK:
        r = DB.execute("SELECT balance FROM customers WHERE customer_id=?", (cid,)).fetchone()
    if not r:
        raise HTTPException(404, "customer not found")
    return r["balance"]


def expire_pauses() -> None:
    """A pause ends after PAUSE_MINUTES. The operation is then cancelled (nothing moves) and
    the customer may start a new one, which is scored again. A hold never expires."""
    t = now()
    with LOCK:
        rows = DB.execute("SELECT * FROM decisions WHERE status='held' AND decision='pause' "
                          "AND pause_until IS NOT NULL").fetchall()
        due = [dict(r) for r in rows if parse(r["pause_until"]) <= t]
        for d in due:
            DB.execute("UPDATE decisions SET status='expired' WHERE decision_id=?", (d["decision_id"],))
        DB.commit()
    for d in due:
        d["reasons"] = json.loads(d["reasons"])
        log_event("pause_expired", d, comment="pause ended: operation cancelled, nothing moved")


def get_decision(did: str) -> dict:
    expire_pauses()
    with LOCK:
        r = DB.execute("SELECT * FROM decisions WHERE decision_id=?", (did,)).fetchone()
    if not r:
        raise HTTPException(404, "decision not found")
    d = dict(r)
    d["reasons"] = json.loads(d["reasons"])
    return d


# ------------------------------------------------------------------- models
class OpIn(BaseModel):
    operation_id: str
    customer_id: str
    channel: str = Field(pattern="^(atm|cash_desk|app)$")
    type: str = Field(pattern="^(cash_withdrawal|transfer)$")
    amount_kzt: int = Field(gt=0)
    payee_id: Optional[str] = None
    payee_type: Optional[str] = None
    payee_known: bool = False
    terminal_id: Optional[str] = None
    timestamp: Optional[str] = None
    extra: dict = {}


class AnswerIn(BaseModel):
    answer: str = Field(pattern="^(yes|no)$")


class OverrideIn(BaseModel):
    action: str = Field(pattern="^(release|confirm_fraud)$")
    comment: str = Field(min_length=3)


class ReportIn(BaseModel):
    customer_id: str


class ConsentIn(BaseModel):
    customer_id: str
    contact_name: str
    contact_chat: str = ""


# --------------------------------------------------------------- core logic
def make_decision(body: OpIn) -> dict:
    if body.timestamp and not ALLOW_CLIENT_TIMESTAMP:
        raise HTTPException(422, "timestamp is set by the host; omit it")
    ts = parse(body.timestamp) if body.timestamp else now()
    if body.amount_kzt > balance_of(body.customer_id):
        d = {"decision_id": None, "operation_id": body.operation_id, "customer_id": body.customer_id,
             "channel": body.channel, "decision": "insufficient_funds", "score": None, "reasons": [],
             "amount_kzt": body.amount_kzt, "result": "decline"}
        log_event("insufficient_funds", d, actor="host", comment=f"amount {body.amount_kzt} above balance")
        return d
    cust, ev, hist, _ = customer_state(body.customer_id, ts)
    op = Operation(body.operation_id, ts, body.channel, body.type, body.amount_kzt, body.payee_id,
                   body.payee_type, body.payee_known, body.terminal_id,
                   (body.extra or {}).get("phone_at_ear_sec"))
    t0 = datetime.now()
    try:
        res = POOL.submit(run_engine, op, cust, ev, hist).result(timeout=ENGINE_TIMEOUT)
    except (FutTimeout, Exception):
        d = {"decision_id": f"d_{uuid.uuid4().hex[:8]}", "operation_id": body.operation_id,
             "customer_id": body.customer_id, "channel": body.channel, "decision": "allow",
             "score": 0, "reasons": [], "engine_available": False}
        log_event("engine_unavailable", d, comment="host approved: fail-open policy")
        apply_executed(body.customer_id, ts, body.type, body.amount_kzt, False)
        d["result"] = "approve"
        return d
    latency = int((datetime.now() - t0).total_seconds() * 1000)
    did = f"d_{uuid.uuid4().hex[:8]}"
    pause_until = iso(ts + timedelta(minutes=PAUSE_MINUTES)) if res.decision == "pause" else None
    status = {"allow": "approved", "ask": "open", "pause": "held", "hold": "held"}[res.decision]
    with LOCK:
        DB.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (did, body.operation_id, body.customer_id, body.channel, body.type, body.amount_kzt,
                    iso(ts), res.decision, res.score, json.dumps(res.reasons, ensure_ascii=False),
                    status, pause_until, body.payee_id, body.payee_type, int(body.payee_known)))
        DB.commit()
    d = {"decision_id": did, "operation_id": body.operation_id, "customer_id": body.customer_id,
         "channel": body.channel, "decision": res.decision, "score": res.score, "reasons": res.reasons,
         "pause_until": pause_until, "rules_version": res.rules_version, "latency_ms": latency,
         "engine_available": True, "amount_kzt": body.amount_kzt}
    log_event("decision", d)
    if res.decision == "allow":
        apply_executed(body.customer_id, ts, body.type, body.amount_kzt, False)
        d["result"] = "approve"
    elif res.decision == "ask":
        d["result"] = "ask"
    else:
        d["result"] = "hold"
        notify_trusted(d)
    return d


def once(key: str, body: OpIn) -> dict:
    """Process an operation at most once per key: same body -> stored answer, other body -> 409."""
    h = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    with LOCK:   # held for the whole call, so two parallel retries cannot both go through
        row = DB.execute("SELECT * FROM idem WHERE key=?", (key,)).fetchone()
        if row:
            if row["body_hash"] != h:
                raise HTTPException(409, "key reused with a different body")
            return json.loads(row["response"])
        d = make_decision(body)
        DB.execute("INSERT INTO idem VALUES (?,?,?,?)", (key, h, json.dumps(d, ensure_ascii=False), iso(now())))
        DB.commit()
    return d


# ---------------------------------------------------------------- endpoints
@app.get("/healthz")
def healthz():
    return {"status": "ok", "rules_version": RULES.get("version")}


@api.get("/v1/customers")
def customers():
    with LOCK:
        return [dict(r) for r in DB.execute("SELECT * FROM customers")]


@api.post("/mock-host/authorize")
def authorize(body: OpIn):
    """Bank authorization host: asks the engine, answers approve / ask / hold / decline.
    A repeated operation_id returns the first answer instead of moving money twice."""
    return once(f"op:{body.operation_id}", body)


@api.post("/v1/decisions")
def decisions(body: OpIn, idempotency_key: str = Header(alias="Idempotency-Key")):
    return once(f"key:{idempotency_key}", body)


@api.get("/v1/decisions/{did}")
def decision_status(did: str):
    return get_decision(did)


@api.post("/v1/decisions/{did}/answer")
def answer(did: str, body: AnswerIn):
    d = get_decision(did)
    if d["status"] != "open":
        raise HTTPException(409, "decision already closed")
    ts = parse(d["ts"])
    if body.answer == "yes":
        with LOCK:
            DB.execute("UPDATE decisions SET status='held', decision='pause', pause_until=? WHERE decision_id=?",
                       (iso(ts + timedelta(minutes=PAUSE_MINUTES)), did))
            DB.commit()
        d = get_decision(did)
        log_event("answer", d, actor="customer", comment="yes: they are asking me by phone")
        notify_trusted(d)
        return {"result": "hold", "decision": "pause", "pause_until": d["pause_until"]}
    if d["amount"] > balance_of(d["customer_id"]):
        raise HTTPException(409, "insufficient funds")
    with LOCK:
        DB.execute("UPDATE decisions SET status='approved' WHERE decision_id=?", (did,))
        DB.commit()
    apply_executed(d["customer_id"], ts, d["type"], d["amount"], True)
    log_event("answer", d, actor="customer", comment="no: my own decision")
    return {"result": "approve"}


@api.post("/v1/decisions/{did}/override")
def override(did: str, body: OverrideIn, x_officer_id: str = Header(default="")):
    if not x_officer_id:
        raise HTTPException(401, "X-Officer-Id required")
    d = get_decision(did)
    if d["status"] != "held":
        raise HTTPException(409, "decision is not on hold")
    ts = parse(d["ts"])
    if body.action == "release":
        if d["amount"] > balance_of(d["customer_id"]):
            raise HTTPException(409, "insufficient funds: the balance changed while on hold")
        with LOCK:
            DB.execute("UPDATE decisions SET status='approved' WHERE decision_id=?", (did,))
            DB.commit()
        apply_executed(d["customer_id"], ts, d["type"], d["amount"], False)
        log_event("override", d, actor=f"officer:{x_officer_id}", comment=f"release (false alarm): {body.comment}")
        return {"result": "approve"}
    with LOCK:
        DB.execute("UPDATE decisions SET status='declined' WHERE decision_id=?", (did,))
        DB.commit()
    log_event("override", d, actor=f"officer:{x_officer_id}", comment=f"confirm_fraud: {body.comment}")
    return {"result": "decline"}


@api.post("/v1/reports")
def report(body: ReportIn):
    with LOCK:
        if not DB.execute("SELECT 1 FROM customers WHERE customer_id=?", (body.customer_id,)).fetchone():
            raise HTTPException(404, "customer not found")
        DB.execute("UPDATE customers SET report_at=? WHERE customer_id=?", (iso(now()), body.customer_id))
        DB.commit()
    log_event("report", actor="customer", customer_id=body.customer_id,
              comment="Scammer on the line: protection on for 24h")
    return {"status": "protected_24h"}


@api.post("/v1/consents")
def consent_create(body: ConsentIn):
    with LOCK:
        if not DB.execute("SELECT 1 FROM customers WHERE customer_id=?", (body.customer_id,)).fetchone():
            raise HTTPException(404, "customer not found")
        cid = f"k_{uuid.uuid4().hex[:6]}"
        DB.execute("INSERT INTO consents VALUES (?,?,?,?,?,NULL)",
                   (cid, body.customer_id, body.contact_name, body.contact_chat, iso(now())))
        DB.commit()
    log_event("consent_given", actor="customer", customer_id=body.customer_id, comment=body.contact_name)
    return {"consent_id": cid}


@api.delete("/v1/consents/{consent_id}")
def consent_revoke(consent_id: str):
    eff = now() + timedelta(hours=24)   # a scammer cannot make the victim revoke mid-call
    with LOCK:
        r = DB.execute("SELECT * FROM consents WHERE consent_id=?", (consent_id,)).fetchone()
        if not r:
            raise HTTPException(404, "consent not found")
        DB.execute("UPDATE consents SET revoke_effective_at=? WHERE consent_id=?", (iso(eff), consent_id))
        DB.commit()
    log_event("consent_revoke_requested", actor="customer", customer_id=r["customer_id"],
              comment="effective in 24h")
    return {"revoke_effective_at": iso(eff)}


@api.get("/v1/events")
def events(limit: int = 100):
    with LOCK:
        rows = [dict(r) for r in DB.execute("SELECT * FROM events ORDER BY event_id DESC LIMIT ?", (limit,))]
    for r in rows:
        r["reasons"] = json.loads(r["reasons"] or "[]")
        r["event_id"] = f"e_{r['event_id']:06d}"
    return rows


@api.get("/v1/held")
def held():
    expire_pauses()
    with LOCK:
        rows = [r["decision_id"] for r in DB.execute("SELECT decision_id FROM decisions WHERE status='held'")]
    return [get_decision(x) for x in rows]


@app.websocket("/v1/events/stream")
async def stream(ws: WebSocket):
    global LOOP
    if not hmac.compare_digest(ws.headers.get("x-service-token", ""), SERVICE_TOKEN):
        await ws.close(code=1008)   # policy violation: no token
        return
    await ws.accept()
    LOOP = asyncio.get_running_loop()   # also works when startup events did not run
    WS_CLIENTS.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        WS_CLIENTS.discard(ws)


@api.post("/v1/demo-reset", dependencies=[Depends(need_demo)])
def demo_reset():
    seed()
    FORCE_ENGINE_DOWN["on"] = os.getenv("ENGINE_FORCE_DOWN") == "1"
    return {"status": "reset"}


@api.post("/v1/demo-time-skip", dependencies=[Depends(need_demo)])
def demo_time_skip(hours: int = 24):
    """DEMO ONLY: simulate time passing by moving every stored event `hours` into the past
    (loans, closed deposits, reports, executed operations, pending consent revocations).
    Used by the blind red team so a tester can 'wait a day' without waiting. The engine is not touched."""
    if not 1 <= hours <= 24 * 14:
        raise HTTPException(422, "hours must be between 1 and 336")
    delta = timedelta(hours=hours)
    with LOCK:
        for col in ("loan_issued_at", "deposit_closed_at", "report_at"):
            for r in DB.execute(f"SELECT customer_id, {col} AS v FROM customers WHERE {col} IS NOT NULL").fetchall():
                DB.execute(f"UPDATE customers SET {col}=? WHERE customer_id=?", (iso(parse(r["v"]) - delta), r["customer_id"]))
        for r in DB.execute("SELECT id, ts FROM history").fetchall():
            DB.execute("UPDATE history SET ts=? WHERE id=?", (iso(parse(r["ts"]) - delta), r["id"]))
        for r in DB.execute("SELECT decision_id, ts, pause_until FROM decisions").fetchall():
            DB.execute("UPDATE decisions SET ts=?, pause_until=? WHERE decision_id=?",
                       (iso(parse(r["ts"]) - delta),
                        iso(parse(r["pause_until"]) - delta) if r["pause_until"] else None, r["decision_id"]))
        for r in DB.execute("SELECT consent_id, revoke_effective_at AS v FROM consents WHERE revoke_effective_at IS NOT NULL").fetchall():
            DB.execute("UPDATE consents SET revoke_effective_at=? WHERE consent_id=?", (iso(parse(r["v"]) - delta), r["consent_id"]))
        DB.commit()
    log_event("demo_time_skip", actor="demo", comment=f"all stored events moved {hours} h into the past")
    return {"skipped_hours": hours}


@api.post("/v1/demo-engine-down", dependencies=[Depends(need_demo)])
def demo_engine_down(down: bool = True):
    FORCE_ENGINE_DOWN["on"] = down
    return {"engine_down": down}


app.include_router(api)
