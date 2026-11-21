import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.api import main  # noqa: E402

main.DEMO_MODE = True              # demo endpoints are off unless DEMO_MODE=1
TOKEN = {"X-Service-Token": main.SERVICE_TOKEN}
client = TestClient(main.app, headers=TOKEN)   # the trusted terminal network (proxy adds the token)
anon = TestClient(main.app)                    # someone calling the API directly
_n = [0]


@pytest.fixture(autouse=True)
def reset():
    client.post("/v1/demo-reset")
    main.FORCE_ENGINE_DOWN["on"] = False
    main.DEMO_MODE = True
    main.ALLOW_CLIENT_TIMESTAMP = False


def body(cid="c_gulnar", amount=500_000, channel="atm", typ="cash_withdrawal", **kw):
    _n[0] += 1
    b = dict(operation_id=f"op_{_n[0]}", customer_id=cid, channel=channel, type=typ, amount_kzt=amount)
    b.update(kw)
    return b


def test_healthz():
    assert client.get("/healthz").json()["status"] == "ok"


def test_ordinary_withdrawal_is_approved():
    r = client.post("/mock-host/authorize", json=body("c_marat", 20_000)).json()
    assert r["result"] == "approve" and r["decision"] == "allow"


def test_scenario_b_ask_no_then_pause():
    first = client.post("/mock-host/authorize", json=body()).json()
    assert first["result"] == "ask" and first["reasons"]
    assert client.post(f"/v1/decisions/{first['decision_id']}/answer", json={"answer": "no"}).json()["result"] == "approve"
    second = client.post("/mock-host/authorize", json=body(terminal_id="atm_2")).json()
    assert second["result"] == "hold" and second["decision"] in ("pause", "hold")
    assert "S11" in [r["signal"] for r in second["reasons"]]


def test_answer_yes_goes_to_pause():
    first = client.post("/mock-host/authorize", json=body()).json()
    r = client.post(f"/v1/decisions/{first['decision_id']}/answer", json={"answer": "yes"}).json()
    assert r["result"] == "hold" and r["decision"] == "pause"


def test_answer_on_closed_decision_is_409():
    first = client.post("/mock-host/authorize", json=body()).json()
    client.post(f"/v1/decisions/{first['decision_id']}/answer", json={"answer": "no"})
    assert client.post(f"/v1/decisions/{first['decision_id']}/answer", json={"answer": "no"}).status_code == 409


def test_cash_desk_and_app_channels():
    r = client.post("/mock-host/authorize", json=body("c_bolat", 2_500_000, channel="cash_desk")).json()
    assert r["decision"] in ("pause", "hold")
    r = client.post("/mock-host/authorize", json=body("c_aigerim", 2_000_000, channel="app", typ="transfer",
                                                     payee_type="individual")).json()
    assert r["decision"] in ("pause", "hold")


def test_officer_release_and_confirm_fraud():
    r = client.post("/mock-host/authorize", json=body("c_bolat", 2_500_000, channel="cash_desk")).json()
    did = r["decision_id"]
    assert client.post(f"/v1/decisions/{did}/override", json={"action": "release", "comment": "no officer id"}).status_code == 401
    rel = client.post(f"/v1/decisions/{did}/override", headers={"X-Officer-Id": "o_01"},
                      json={"action": "release", "comment": "bought a car, confirmed by phone"})
    assert rel.json()["result"] == "approve"
    assert client.post(f"/v1/decisions/{did}/override", headers={"X-Officer-Id": "o_01"},
                       json={"action": "release", "comment": "again"}).status_code == 409
    r2 = client.post("/mock-host/authorize", json=body("c_gulnar", 2_500_000, channel="cash_desk")).json()
    fr = client.post(f"/v1/decisions/{r2['decision_id']}/override", headers={"X-Officer-Id": "o_01"},
                     json={"action": "confirm_fraud", "comment": "victim confirmed coaching"})
    assert fr.json()["result"] == "decline"


def test_override_requires_comment():
    r = client.post("/mock-host/authorize", json=body("c_bolat", 2_500_000, channel="cash_desk")).json()
    assert client.post(f"/v1/decisions/{r['decision_id']}/override", headers={"X-Officer-Id": "o"},
                       json={"action": "release", "comment": ""}).status_code == 422


def test_report_button_raises_risk():
    assert client.post("/v1/reports", json={"customer_id": "c_marat"}).json()["status"] == "protected_24h"
    r = client.post("/mock-host/authorize", json=body("c_marat", 20_000)).json()
    assert "S8" in [x["signal"] for x in r["reasons"]] and r["decision"] == "ask"


def test_notification_needs_consent():
    kinds = lambda: [e["kind"] for e in client.get("/v1/events").json()]
    client.post("/mock-host/authorize", json=body("c_bolat", 2_500_000, channel="cash_desk"))
    assert "notify_skipped_no_consent" in kinds() and "notify_sent" not in kinds()
    client.post("/mock-host/authorize", json=body("c_gulnar", 2_500_000, channel="cash_desk"))
    assert "notify_sent" in kinds()


def test_consent_create_and_delayed_revoke():
    cid = client.post("/v1/consents", json={"customer_id": "c_bolat", "contact_name": "Son"}).json()["consent_id"]
    assert client.delete(f"/v1/consents/{cid}").json()["revoke_effective_at"]
    client.post("/mock-host/authorize", json=body("c_bolat", 2_500_000, channel="cash_desk"))
    assert "notify_sent" in [e["kind"] for e in client.get("/v1/events").json()]  # still active within 24h


def test_decisions_requires_token_and_is_idempotent():
    b = body("c_marat", 20_000)
    assert anon.post("/v1/decisions", json=b, headers={"Idempotency-Key": "k1"}).status_code == 401
    h = {**TOKEN, "Idempotency-Key": "k1"}
    a = client.post("/v1/decisions", json=b, headers=h).json()
    again = client.post("/v1/decisions", json=b, headers=h).json()
    assert a["decision_id"] == again["decision_id"]
    other = dict(b, amount_kzt=30_000)
    assert client.post("/v1/decisions", json=other, headers=h).status_code == 409
    n = sum(1 for e in client.get("/v1/events").json() if e["kind"] == "decision")
    assert n == 1


def test_validation_errors():
    assert client.post("/mock-host/authorize", json=body(amount=0)).status_code == 422
    assert client.post("/mock-host/authorize", json=body(channel="fax")).status_code == 422
    assert client.post("/mock-host/authorize", json=body(cid="nobody")).status_code == 404
    assert client.post("/mock-host/authorize", json={"customer_id": "c_marat"}).status_code == 422


def test_engine_down_is_fail_open():
    main.FORCE_ENGINE_DOWN["on"] = True
    r = client.post("/mock-host/authorize", json=body()).json()
    assert r["result"] == "approve" and r["engine_available"] is False
    assert "engine_unavailable" in [e["kind"] for e in client.get("/v1/events").json()]


def test_events_stream_websocket():
    with client.websocket_connect("/v1/events/stream", headers=TOKEN) as ws:
        client.post("/mock-host/authorize", json=body("c_marat", 10_000))
        ev = ws.receive_json()
        assert ev["kind"] == "decision"


def test_every_non_allow_event_has_reasons():
    client.post("/mock-host/authorize", json=body())
    for e in client.get("/v1/events").json():
        if e["kind"] == "decision" and e["decision"] != "allow":
            assert e["reasons"]


def test_demo_time_skip_expires_the_fresh_loan_signal():
    first = client.post("/mock-host/authorize", json=body("c_gulnar", 100_000)).json()
    assert "S1" in [r["signal"] for r in first["reasons"]]
    assert client.post("/v1/demo-time-skip?hours=25").json() == {"skipped_hours": 25}
    after = client.post("/mock-host/authorize", json=body("c_gulnar", 100_000)).json()
    assert "S1" not in [r["signal"] for r in after["reasons"]]
    assert "demo_time_skip" in [e["kind"] for e in client.get("/v1/events").json()]


def test_demo_time_skip_validates_hours():
    assert client.post("/v1/demo-time-skip?hours=0").status_code == 422
    assert client.post("/v1/demo-time-skip?hours=9999").status_code == 422


# ---------------------------------------------------------------- bug fixes after the audit (2026-11-19)
def balance(cid):
    return next(c for c in client.get("/v1/customers").json() if c["customer_id"] == cid)["balance"]


def kinds():
    return [e["kind"] for e in client.get("/v1/events").json()]


def test_amount_above_balance_is_declined_and_nothing_moves():
    before = balance("c_marat")
    r = client.post("/mock-host/authorize", json=body("c_marat", 50_000_000))
    assert r.status_code == 200
    assert r.json()["result"] == "decline" and r.json()["decision"] == "insufficient_funds"
    assert balance("c_marat") == before
    assert "insufficient_funds" in kinds()


def test_release_rechecks_the_balance():
    r = client.post("/mock-host/authorize", json=body("c_bolat", 2_500_000, channel="cash_desk")).json()
    assert r["result"] == "hold"
    # meanwhile the balance dropped below the held amount (an approved small payment)
    with main.LOCK:
        main.DB.execute("UPDATE customers SET balance=100000 WHERE customer_id='c_bolat'")
        main.DB.commit()
    rel = client.post(f"/v1/decisions/{r['decision_id']}/override", headers={"X-Officer-Id": "o_01"},
                      json={"action": "release", "comment": "customer confirmed"})
    assert rel.status_code == 409
    assert balance("c_bolat") == 100_000


def test_pause_expires_after_pause_minutes():
    r = client.post("/mock-host/authorize", json=body("c_aigerim", 2_000_000, channel="app", typ="transfer",
                                                     payee_type="individual")).json()
    assert r["decision"] == "pause" and r["pause_until"]
    did = r["decision_id"]
    assert client.get(f"/v1/decisions/{did}").json()["status"] == "held"
    client.post("/v1/demo-time-skip?hours=1")          # longer than the 30-minute pause
    assert client.get(f"/v1/decisions/{did}").json()["status"] == "expired"
    assert did not in [d["decision_id"] for d in client.get("/v1/held").json()]
    assert "pause_expired" in kinds()
    # an expired pause cannot be released any more, and no money moved
    assert client.post(f"/v1/decisions/{did}/override", headers={"X-Officer-Id": "o_01"},
                       json={"action": "release", "comment": "too late"}).status_code == 409
    assert balance("c_aigerim") == 2_000_000


def test_hold_does_not_expire():
    first = client.post("/mock-host/authorize", json=body()).json()
    client.post(f"/v1/decisions/{first['decision_id']}/answer", json={"answer": "no"})
    second = client.post("/mock-host/authorize", json=body()).json()
    assert second["decision"] == "hold"
    client.post("/v1/demo-time-skip?hours=2")
    assert client.get(f"/v1/decisions/{second['decision_id']}").json()["status"] == "held"


def test_demo_endpoints_are_off_without_demo_mode():
    main.DEMO_MODE = False
    for path in ("/v1/demo-reset", "/v1/demo-time-skip?hours=24", "/v1/demo-engine-down?down=true"):
        assert client.post(path).status_code == 404, path
    assert main.FORCE_ENGINE_DOWN["on"] is False
    r = client.post("/mock-host/authorize", json=body("c_gulnar", 2_500_000, channel="cash_desk")).json()
    assert r["engine_available"] is True and r["result"] == "hold"


def test_client_timestamp_is_rejected():
    past = (main.now() - main.timedelta(hours=5)).isoformat()
    r = client.post("/mock-host/authorize", json=body("c_gulnar", 2_500_000, channel="cash_desk", timestamp=past))
    assert r.status_code == 422
    # simulation scripts may switch it on explicitly
    main.ALLOW_CLIENT_TIMESTAMP = True
    r = client.post("/mock-host/authorize", json=body("c_marat", 10_000, timestamp=main.now().isoformat()))
    assert r.status_code == 200


def test_same_operation_id_is_processed_once():
    b = body("c_marat", 20_000)
    before = balance("c_marat")
    a = client.post("/mock-host/authorize", json=b).json()
    again = client.post("/mock-host/authorize", json=b).json()
    assert a["decision_id"] == again["decision_id"]
    assert balance("c_marat") == before - 20_000
    assert client.post("/mock-host/authorize", json=dict(b, amount_kzt=30_000)).status_code == 409


def test_api_needs_the_service_token():
    assert anon.get("/healthz").status_code == 200        # health check stays open
    assert anon.post("/mock-host/authorize", json=body("c_marat", 10_000)).status_code == 401
    assert anon.get("/v1/customers").status_code == 401
    assert anon.post("/v1/decisions/d_x/answer", json={"answer": "no"}).status_code == 401
    assert anon.post("/v1/demo-engine-down?down=true").status_code == 401
    assert main.FORCE_ENGINE_DOWN["on"] is False
    import pytest as _pt
    from starlette.websockets import WebSocketDisconnect as _WD
    with _pt.raises(_WD):
        with anon.websocket_connect("/v1/events/stream") as ws:
            ws.receive_json()
