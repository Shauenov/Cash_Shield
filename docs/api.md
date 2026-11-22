# API contract (as implemented)

Base URL in Docker: `http://localhost:8080/api` (nginx proxy). Direct: `http://localhost:8000`.
Every call except `GET /healthz` needs `X-Service-Token` (the WebSocket too). The screens never send it: the proxy (nginx in Docker, Vite in development) adds it. Officer actions also need `X-Officer-Id` and a comment. The host stamps the operation time from its clock (`services/api/clock.py`); a `timestamp` in the body is always rejected.

| Method and path | Caller | What it does |
|---|---|---|
| `POST /mock-host/authorize` | ATM, cash desk, app | Mock bank authorization host. Checks the balance (`result: decline`, `decision: insufficient_funds` if the amount is above it), calls the engine and answers `result`: `approve`, `ask`, `hold` or `decline`. A repeated `operation_id` returns the first answer (other body: 409). If the engine is silent for 500 ms the host answers `approve` and logs `engine_unavailable` |
| `POST /v1/decisions` | host (service) | Same engine call; needs `X-Service-Token` and `Idempotency-Key` (same key and body = same answer, same key and other body = 409) |
| `GET /v1/decisions/{id}` | screens | Status: `open`, `held`, `approved`, `declined`, `expired` (a pause past `pause_until`: cancelled, nothing moved) |
| `POST /v1/decisions/{id}/answer` | ATM, app | `{"answer": "yes" or "no"}`. `yes` puts the operation on pause; `no` lets it through and marks it for S11 |
| `POST /v1/decisions/{id}/override` | officer console | `{"action": "release" or "confirm_fraud", "comment": "..."}`; header `X-Officer-Id` required |
| `POST /v1/reports` | app | "Scammer on the line": raises risk for that customer for 24 h (S8) |
| `POST /v1/consents`, `DELETE /v1/consents/{id}` | app | Give or withdraw consent for the trusted person. Withdrawal takes effect after 24 h |
| `GET /v1/events`, `WS /v1/events/stream` | officer console | Event log and live stream |
| `GET /v1/held`, `GET /v1/customers` | officer console, screens | Held decisions; demo customers |
| `POST /v1/demo-reset`, `POST /v1/demo-engine-down`, `POST /v1/demo-time-skip?hours=N` | demo only, `DEMO_MODE=1` (404 otherwise) | Reset the database; simulate an engine outage; move the API clock N hours forward, stored data untouched; reset puts the clock back to real time (for the blind red team) |
| `GET /healthz` | Docker, tests | Liveness |

Authorize body (`channel`: atm, cash_desk or app; `type`: cash_withdrawal or transfer):

```json
{
  "operation_id": "op_1", "customer_id": "c_gulnar",
  "channel": "atm",
  "type": "cash_withdrawal",
  "amount_kzt": 500000,
  "payee_id": null, "payee_type": null, "payee_known": false,
  "terminal_id": "atm_017",
  "extra": { "phone_at_ear_sec": null }
}
```

Decision response: `decision` (`allow`, `ask`, `pause` or `hold`), `score`, `reasons` (`signal`, `contribution`, `text_ru`, `text_en`), `pause_until`, `pause_seconds_left` (by the server clock; screens count down from it), `rules_version`, `latency_ms`.

Errors: 401 bad token or missing officer id, 404 unknown customer or decision (or demo endpoint with `DEMO_MODE` off), 409 closed decision, reused key or operation id, or not enough money at release, 422 bad body or a client `timestamp`.
