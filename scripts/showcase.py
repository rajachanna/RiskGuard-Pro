"""One command: entirely offline, no account, key or network needed."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from fastapi.testclient import TestClient

from riskguard.api import Settings, create_app


API_KEY = "offline-demo-operator-key-for-tests"


def main():
    with TemporaryDirectory(prefix="riskguard-demo-") as directory:
        client = TestClient(create_app(settings=Settings(
            operator_key=API_KEY, db_path=Path(directory) / "demo.sqlite")))
        auth = {"X-API-Key": API_KEY}
        account = client.get("/api/demo-portfolio", headers=auth).json()
        intent = {"venue": "PAPER_CEX", "symbol": "BTCUSDT", "side": "BUY",
                  "quantity": "0.01", "entry_price": "65000", "stop_price": "64000",
                  "target_price": "68000", "quote_as_of": datetime.now(timezone.utc).isoformat()}

        def case(title, changes=None):
            current = {**intent, **(changes or {})}
            response = client.post("/api/review", json={"intent": current, "portfolio": account}, headers=auth)
            response.raise_for_status()
            result = response.json()
            failed = [x["code"] for x in result["rules"] if not x["passed"]]
            print(f"{title}: {result['decision']} | failed_rules={failed} | executed={result['order_executed']}")
            return result

        print("RiskGuard Pro — synthetic review only / NEVER executes orders")
        assert case("01 Valid example")["decision"] == "APPROVE"
        assert case("02 Low reward/risk", {"target_price": "65100"})["decision"] == "REJECT"
        assert case("03 Excessive size", {"quantity": "0.1"})["decision"] == "REJECT"
        client.post("/api/control/halt", headers=auth).raise_for_status()
        assert case("04 Emergency halt")["decision"] == "REJECT"
        client.post("/api/control/resume", headers=auth).raise_for_status()
        report = client.get("/api/stress", headers=auth).json()
        print("Illustrative stress:", json.dumps(report["scenarios"], indent=2))
        history = client.get("/api/history", headers=auth).json()["reviews"]
        print(f"PASS: {len(history)} reviews audited; no orders or external market requests.")


if __name__ == "__main__":
    main()
