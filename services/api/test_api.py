import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.api import main  # noqa: E402

client = TestClient(main.app)
TOKEN = {"X-Service-Token": "change-me"}
_n = [0]


@pytest.fixture(autouse=True)
def reset():
    client.post("/v1/demo-reset")
    main.FORCE_ENGINE_DOWN["on"] = False


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
    assert client.post("/v1/decisions", json=b, headers={"Idempotency-Key": "k1"}).status_code == 401
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
    with client.websocket_connect("/v1/events/stream") as ws:
        client.post("/mock-host/authorize", json=body("c_marat", 10_000))
        ev = ws.receive_json()
        assert ev["kind"] == "decision"


def test_every_non_allow_event_has_reasons():
    client.post("/mock-host/authorize", json=body())
    for e in client.get("/v1/events").json():
        if e["kind"] == "decision" and e["decision"] != "allow":
            assert e["reasons"]
