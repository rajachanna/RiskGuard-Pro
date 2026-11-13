from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from riskguard.api import Settings, create_app

AUTH = {"X-API-Key": "test-operator-key-very-long-12345"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(settings=Settings(
        operator_key=AUTH["X-API-Key"], db_path=tmp_path / "audits.sqlite")))


def example_payload(client):
    portfolio = client.get("/api/demo-portfolio", headers=AUTH).json()
    return {
        "portfolio": portfolio,
        "intent": {"venue": "PAPER_CEX", "symbol": "BTCUSDT", "side": "BUY",
                   "quantity": "0.01", "entry_price": "65000", "stop_price": "64000",
                   "target_price": "68000", "quote_as_of": datetime.now(timezone.utc).isoformat()},
    }


def test_health_unrestricted_and_contains_no_trading(client):
    assert client.get("/health").json()["broker_orders_enabled"] is False
    assert "RiskGuard Pro" in client.get("/").text
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("path", [
    "/api/policy", "/api/demo-portfolio", "/api/stress", "/api/history", "/api/control",
])
def test_protected_reads(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get(path, headers=AUTH).status_code == 200


def test_review_requires_auth(client):
    payload = example_payload(client)
    assert client.post("/api/review", json=payload).status_code == 401
    assert client.post("/api/review", headers=AUTH, json=payload).status_code == 200


def test_approve_and_audit_review(client):
    response = client.post("/api/review", headers=AUTH, json=example_payload(client))
    assert response.status_code == 200
    assert response.json()["decision"] == "APPROVE"
    assert response.json()["order_executed"] is False
    rows = client.get("/api/history", headers=AUTH).json()["reviews"]
    assert len(rows) == 1 and rows[0]["decision"] == "APPROVE"


def test_reject_shows_reason(client):
    payload = example_payload(client)
    payload["intent"]["target_price"] = "65100"
    response = client.post("/api/review", headers=AUTH, json=payload)
    assert response.status_code == 200
    assert response.json()["decision"] == "REJECT"
    assert any(x["code"] == "REWARD_RISK" and not x["passed"] for x in response.json()["rules"])
    assert "REWARD_RISK" in client.get("/api/history", headers=AUTH).json()["reviews"][0]["failed_rules"]


def test_halt_resume_blocks_review(client):
    assert client.post("/api/control/halt", headers=AUTH).json()["halted"] is True
    result = client.post("/api/review", headers=AUTH, json=example_payload(client)).json()
    assert result["decision"] == "REJECT"
    assert any(x["code"] == "EMERGENCY_HALT" and not x["passed"] for x in result["rules"])
    assert client.post("/api/control/resume", headers=AUTH).json()["halted"] is False
    assert client.post("/api/review", headers=AUTH, json=example_payload(client)).json()["decision"] == "APPROVE"


def test_controls_cannot_change_without_key(client):
    assert client.post("/api/control/halt").status_code == 401
    assert client.get("/api/control", headers=AUTH).json()["halted"] is False


def test_stress_is_not_var(client):
    result = client.get("/api/stress", headers=AUTH).json()
    assert result["mode"] == "SYNTHETIC_STRESS_ONLY"
    assert Decimal(result["scenarios"][-1]["projected_equity_usd"]) == Decimal("9500")


def test_fail_closed_key_not_configured(tmp_path):
    client = TestClient(create_app(settings=Settings(
        operator_key="REPLACE_WITH_RANDOM_OPERATOR_KEY", db_path=tmp_path / "db.sqlite")))
    assert client.get("/api/policy", headers={"X-API-Key": "REPLACE_WITH_RANDOM_OPERATOR_KEY"}).status_code == 401


def test_snapshot_never_mutates_on_review(client):
    before = client.get("/api/demo-portfolio", headers=AUTH).json()
    client.post("/api/review", headers=AUTH, json=example_payload(client))
    after = client.get("/api/demo-portfolio", headers=AUTH).json()
    assert before["cash_usd"] == after["cash_usd"]
    assert before["positions"][0]["quantity"] == after["positions"][0]["quantity"]


def test_api_blocks_live_accounts(client):
    payload = example_payload(client)
    payload["intent"]["venue"] = "LIVE_IBKR"
    assert client.post("/api/review", headers=AUTH, json=payload).status_code == 422


def test_unknown_extra_fields_rejected(client):
    payload = example_payload(client)
    payload["intent"]["execute"] = True
    assert client.post("/api/review", headers=AUTH, json=payload).status_code == 422
