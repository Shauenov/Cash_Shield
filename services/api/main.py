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
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
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

from engine import decide, load_rules  # noqa: E402
from services.api.clock import TZ, ShiftedClock  # noqa: E402
from services.api.ledger import SqliteLedger  # noqa: E402
from services.api.lifecycle import Conflict, Lifecycle, NotFound, OpRequest  # noqa: E402

# All business time comes from here (see clock.py). Tests and the red team swap in a ManualClock.
CLOCK = ShiftedClock()
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "change-me")
ENGINE_TIMEOUT = float(os.getenv("ENGINE_TIMEOUT_MS", "500")) / 1000
PAUSE_MINUTES = int(os.getenv("PAUSE_MINUTES", "30"))
DB_PATH = os.getenv("DB_PATH", ":memory:")
RULES_PATH = os.getenv("RULES_PATH")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_DEMO_CHAT_ID", "")
# Demo-only endpoints (reset, time skip, engine outage switch) exist only when DEMO_MODE=1.
DEMO_MODE = os.getenv("DEMO_MODE") == "1"

RULES = load_rules(Path(RULES_PATH) if RULES_PATH else None)
LOCK = threading.RLock()
FORCE_ENGINE_DOWN = {"on": os.getenv("ENGINE_FORCE_DOWN") == "1"}  # test/demo switch

@asynccontextmanager
async def lifespan(_app):
    global LOOP
    LOOP = asyncio.get_running_loop()
    yield


app = FastAPI(title="Cash Shield", version="0.1", lifespan=lifespan)
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
    return CLOCK.now()


def seconds_left(pause_until: Optional[str]) -> Optional[int]:
    """Seconds until the pause ends, by the server's clock (the screens do not use their own)."""
    if not pause_until:
        return None
    return max(0, int((parse(pause_until) - now()).total_seconds()))


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


def need_token(x_service_token: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_service_token, SERVICE_TOKEN):
        raise HTTPException(401, "bad or missing X-Service-Token")


def need_demo() -> None:
    if not DEMO_MODE:
        raise HTTPException(404, "not found")


# Every endpoint except /healthz needs the service token. The screens get it from the
# reverse proxy (nginx in Docker, Vite in development), which plays the bank's terminal network.
api = APIRouter(dependencies=[Depends(need_token)])


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
    if not (TELEGRAM_BOT_TOKEN and c.get("contact_chat")):
        log_event("notify_sent", d, comment="simulated: " + c["contact_name"])
        return
    try:
        import httpx
        r = httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                       json={"chat_id": c["contact_chat"], "text": text}, timeout=3)
        r.raise_for_status()
    except Exception as e:   # the bank must see that the relative was NOT told
        log_event("notify_failed", d, comment=f"telegram error ({type(e).__name__}): " + c["contact_name"])
        return
    log_event("notify_sent", d, comment="telegram: " + c["contact_name"])


class _ApiClock:
    """Reads main.CLOCK on every call, so tests and the red team can swap the clock."""

    def now(self):
        return CLOCK.now()


# The decision lifecycle (services/api/lifecycle.py) owns every transition and every money
# movement. The routes below only translate HTTP to its interface and back.
LIFECYCLE = Lifecycle(
    SqliteLedger(DB, LOCK), _ApiClock(), rules=RULES, pause_minutes=PAUSE_MINUTES,
    events=lambda kind, rec, actor, comment: log_event(kind, rec, actor=actor, comment=comment),
    notify=lambda rec: notify_trusted(rec),
    engine=lambda op, cust, ev, hist: run_engine(op, cust, ev, hist), timeout=ENGINE_TIMEOUT)


def as_json(rec: dict) -> dict:
    d = dict(rec, ts=iso(rec["ts"]), pause_until=iso(rec["pause_until"]))
    d["pause_seconds_left"] = seconds_left(d["pause_until"]) if d["status"] in ("held", "expired") else None
    return d


def get_decision(did: str) -> dict:
    try:
        return as_json(LIFECYCLE.current(did))
    except NotFound:
        raise HTTPException(404, "decision not found")


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
    payee_company_age_days: Optional[int] = Field(default=None, ge=0)   # v2 rules: from the state register
    timestamp: Optional[str] = None   # never accepted: the host stamps the time (422 if sent)
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
    if body.timestamp:
        raise HTTPException(422, "timestamp is set by the host; omit it")
    req = OpRequest(body.operation_id, body.customer_id, body.channel, body.type, body.amount_kzt,
                    body.payee_id, body.payee_type, body.payee_known, body.terminal_id,
                    (body.extra or {}).get("phone_at_ear_sec"), body.payee_company_age_days,
                    (body.extra or {}).get("camera_blocked") is True)
    t0 = time.perf_counter()   # real time: latency is not affected by the demo clock
    try:
        out = LIFECYCLE.submit(req)
    except KeyError:
        raise HTTPException(404, "customer not found")
    d = {"decision_id": out.decision_id, "operation_id": body.operation_id, "customer_id": body.customer_id,
         "channel": body.channel, "decision": out.decision, "score": out.score, "reasons": out.reasons,
         "pause_until": iso(out.pause_until), "pause_seconds_left": out.pause_seconds_left,
         "amount_kzt": body.amount_kzt, "result": out.result, "engine_available": out.engine_available}
    if out.decision != "insufficient_funds" and out.engine_available:
        d.update(rules_version=str(RULES.get("version", "")), latency_ms=int((time.perf_counter() - t0) * 1000))
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
    try:
        with LOCK:
            out = LIFECYCLE.answer(did, yes=body.answer == "yes")
    except NotFound:
        raise HTTPException(404, "decision not found")
    except Conflict as e:
        raise HTTPException(409, str(e))
    if out.result == "hold":
        return {"result": "hold", "decision": "pause", "pause_until": iso(out.pause_until),
                "pause_seconds_left": out.pause_seconds_left}
    return {"result": "approve"}


@api.post("/v1/decisions/{did}/override")
def override(did: str, body: OverrideIn, x_officer_id: str = Header(default="")):
    if not x_officer_id:
        raise HTTPException(401, "X-Officer-Id required")
    step = LIFECYCLE.release if body.action == "release" else LIFECYCLE.confirm_fraud
    try:
        with LOCK:
            out = step(did, officer=x_officer_id, comment=body.comment)
    except NotFound:
        raise HTTPException(404, "decision not found")
    except Conflict as e:
        raise HTTPException(409, str(e))
    return {"result": out.result}


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
    with LOCK:
        rows = LIFECYCLE.ledger.held_ids()
        recs = [get_decision(x) for x in rows]   # a pause past its end turns `expired` here
    return [r for r in recs if r["status"] == "held"]


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
    CLOCK.reset()
    seed()
    FORCE_ENGINE_DOWN["on"] = os.getenv("ENGINE_FORCE_DOWN") == "1"
    return {"status": "reset"}


@api.post("/v1/demo-time-skip", dependencies=[Depends(need_demo)])
def demo_time_skip(hours: int = 24):
    """DEMO ONLY: let `hours` pass by moving the clock forward. Stored data is not touched.
    "Reset demo" moves the clock back to real time. Used by the blind red team so a tester can
    'wait a day' without waiting. The engine is not touched."""
    if not 1 <= hours <= 24 * 14:
        raise HTTPException(422, "hours must be between 1 and 336")
    CLOCK.advance(timedelta(hours=hours))
    log_event("demo_time_skip", actor="demo", comment=f"clock moved {hours} h forward")
    return {"skipped_hours": hours}


@api.post("/v1/demo-engine-down", dependencies=[Depends(need_demo)])
def demo_engine_down(down: bool = True):
    FORCE_ENGINE_DOWN["on"] = down
    return {"engine_down": down}


app.include_router(api)
