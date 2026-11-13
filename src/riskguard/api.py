"""RiskGuard Pro REST API; API decisions are NOT orders and cannot trade."""
from dataclasses import dataclass
from hmac import compare_digest
from pathlib import Path
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from . import __version__
from .audit import AuditStore
from .demo import sample_portfolio
from .engine import review, stress
from .models import ReviewRequest
from .policy import RiskPolicy


@dataclass(frozen=True)
class Settings:
    operator_key: str = ""
    db_path: Path = Path("./data/riskguard.sqlite")

    @classmethod
    def from_env(cls):
        return cls(operator_key=os.getenv("RG_OPERATOR_KEY", ""),
                   db_path=Path(os.getenv("RG_DB_PATH", "./data/riskguard.sqlite")))

    @staticmethod
    def authorized(secret: str) -> bool:
        return len(secret) >= 20 and not secret.startswith("REPLACE_")


def create_app(*, settings: Settings | None = None, policy: RiskPolicy | None = None):
    config = settings or Settings.from_env()
    risk_policy = policy or RiskPolicy()
    risk_policy.validate()
    store: AuditStore | None = None
    app = FastAPI(
        title="RiskGuard Pro — Pre-trade Risk Review",
        version=__version__,
        description="Explains why a fictional USD order is approved or rejected. Never sends broker orders.",
    )

    def authenticated(x_api_key: str | None = Header(default=None)):
        if not (config.authorized(config.operator_key) and x_api_key is not None
                and compare_digest(config.operator_key, x_api_key)):
            raise HTTPException(status_code=401, detail="Invalid operator key")

    def get_store() -> AuditStore:
        nonlocal store
        if store is None:
            try:
                store = AuditStore(config.db_path)
            except OSError as exc:
                raise HTTPException(status_code=503, detail="Local review store unavailable") from exc
        return store

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/health")
    def health():
        return {"ready": True, "version": __version__, "mode": "REVIEW_ONLY", "broker_orders_enabled": False}

    @app.get("/api/policy", dependencies=[Depends(authenticated)])
    def limits():
        return {"mode": "REVIEW_ONLY", "limits": risk_policy.as_dict()}

    @app.get("/api/demo-portfolio", dependencies=[Depends(authenticated)])
    def demo_account():
        return sample_portfolio()

    @app.get("/api/stress", dependencies=[Depends(authenticated)])
    def demo_stress():
        return stress(sample_portfolio())

    @app.post("/api/review", dependencies=[Depends(authenticated)])
    def evaluate(payload: ReviewRequest, audit: AuditStore = Depends(get_store)):
        result = review(payload, policy=risk_policy, halted=audit.halted())
        audit.save_review(payload.intent.venue, payload.intent.symbol, payload.intent.side,
                          result.decision, [rule.code for rule in result.rules if not rule.passed])
        return result

    @app.get("/api/history", dependencies=[Depends(authenticated)])
    def history(audit: AuditStore = Depends(get_store)):
        return audit.history()

    @app.get("/api/control", dependencies=[Depends(authenticated)])
    def current_control(audit: AuditStore = Depends(get_store)):
        return {"halted": audit.halted(), "mode": "REVIEW_ONLY"}

    @app.post("/api/control/halt", dependencies=[Depends(authenticated)])
    def halt(audit: AuditStore = Depends(get_store)):
        return {"halted": audit.set_halt(True), "mode": "REVIEW_ONLY"}

    @app.post("/api/control/resume", dependencies=[Depends(authenticated)])
    def resume(audit: AuditStore = Depends(get_store)):
        return {"halted": audit.set_halt(False), "mode": "REVIEW_ONLY"}

    return app


app = create_app()
