from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from riskguard.demo import sample_portfolio
from riskguard.engine import review, stress
from riskguard.models import Portfolio, ReviewRequest
from riskguard.policy import RiskPolicy


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


def request(now, **changes):
    alert = {
        "venue": "PAPER_CEX", "symbol": "BTCUSDT", "side": "BUY",
        "quantity": "0.01", "entry_price": "65000", "stop_price": "64000",
        "target_price": "68000", "quote_as_of": now.isoformat(),
    }
    alert.update(changes)
    return ReviewRequest.model_validate({"intent": alert, "portfolio": sample_portfolio(now=now)})


def failed(result):
    return {rule.code for rule in result.rules if not rule.passed}


def test_default_buy_approved(now):
    result = review(request(now), now=now)
    assert result.decision == "APPROVE"
    assert result.order_executed is False
    assert result.metrics["estimated_stop_risk_usd"] == "10.00"
    assert result.metrics["order_notional_usd"] == "650.00"
    assert Decimal(result.max_suggested_buy_quantity) >= Decimal("0.01")


def test_target_ratio_too_low(now):
    result = review(request(now, target_price="65300"), now=now)
    assert result.decision == "REJECT"
    assert "REWARD_RISK" in failed(result)


def test_stop_is_required_for_buy(now):
    result = review(request(now, stop_price=None), now=now)
    assert "PROTECTIVE_STOP" in failed(result)
    assert result.max_suggested_buy_quantity is None


def test_stop_above_entry_rejected(now):
    result = review(request(now, stop_price="66000"), now=now)
    assert "PROTECTIVE_STOP" in failed(result)


def test_target_missing_rejected(now):
    assert "PROFIT_TARGET" in failed(review(request(now, target_price=None), now=now))


def test_risk_budget_guard(now):
    result = review(request(now, quantity="0.02", stop_price="58000", target_price="78000"), now=now)
    assert "RISK_PER_TRADE" in failed(result)


def test_max_order_notional(now):
    result = review(request(now, quantity="0.05"), now=now)
    assert "ORDER_NOTIONAL" in failed(result)


def test_symbol_concentration(now):
    # 22 shares at $175 => $3,850, already above 25% limit.
    result = review(request(now, venue="PAPER_IBKR", symbol="AAPL", quantity="12",
                            entry_price="175", stop_price="174", target_price="180"), now=now)
    assert "SYMBOL_EXPOSURE" in failed(result)


def test_gross_exposure(now):
    result = review(request(now), now=now, policy=RiskPolicy(max_gross_exposure_pct=Decimal("28")))
    assert "GROSS_EXPOSURE" in failed(result)


def test_position_count(now):
    result = review(request(now), now=now, policy=RiskPolicy(max_open_positions=2))
    assert "POSITION_COUNT" in failed(result)


def test_cash_limit(now):
    payload = request(now)
    payload.portfolio.cash_usd = Decimal("100")
    payload.portfolio.equity_usd = Decimal("2600")
    payload.portfolio.peak_equity_usd = Decimal("2600")
    result = review(payload, now=now)
    assert "CASH_AVAILABLE" in failed(result)


def test_stale_quote(now):
    result = review(request(now, quote_as_of=(now - timedelta(seconds=65)).isoformat()), now=now)
    assert "QUOTE_FRESHNESS" in failed(result)


def test_future_quote(now):
    result = review(request(now, quote_as_of=(now + timedelta(seconds=10)).isoformat()), now=now)
    assert "QUOTE_FRESHNESS" in failed(result)


def test_stale_portfolio(now):
    req = request(now)
    req.portfolio.as_of = now - timedelta(minutes=3)
    assert "PORTFOLIO_FRESHNESS" in failed(review(req, now=now))


def test_stale_existing_mark(now):
    req = request(now)
    req.portfolio.positions[0].price_as_of = now - timedelta(minutes=4)
    assert "POSITION_MARK_FRESHNESS" in failed(review(req, now=now))


def test_portfolio_reconciliation(now):
    req = request(now)
    req.portfolio.cash_usd = Decimal("7800")
    assert "SYNTHETIC_RECONCILIATION" in failed(review(req, now=now))


def test_emergency_halt(now):
    assert "EMERGENCY_HALT" in failed(review(request(now), now=now, halted=True))


def test_drawdown_rejects_buy(now):
    req = request(now)
    req.portfolio.peak_equity_usd = Decimal("12000")
    assert "DRAWDOWN_GUARD" in failed(review(req, now=now))


def test_daily_realized_loss_rejects_buy(now):
    req = request(now)
    req.portfolio.daily_realized_pnl_usd = Decimal("-350")
    assert "DAILY_REALIZED_LOSS" in failed(review(req, now=now))


def test_sell_existing_long_allowed_without_stops(now):
    result = review(request(now, venue="PAPER_IBKR", symbol="AAPL", side="SELL",
                            quantity="5", entry_price="180", stop_price=None, target_price=None), now=now)
    assert result.decision == "APPROVE"
    assert result.max_suggested_buy_quantity is None


def test_sell_unknown_rejected(now):
    result = review(request(now, side="SELL", stop_price=None, target_price=None), now=now)
    assert "LONG_ONLY_REDUCTION" in failed(result)


def test_sell_more_than_held_rejected(now):
    result = review(request(now, venue="PAPER_IBKR", symbol="AAPL", side="SELL",
                            quantity="11", entry_price="180", stop_price=None, target_price=None), now=now)
    assert "LONG_ONLY_REDUCTION" in failed(result)


def test_risk_reducing_sell_after_daily_loss(now):
    req = request(now, venue="PAPER_IBKR", symbol="AAPL", side="SELL",
                  quantity="2", entry_price="180", stop_price=None, target_price=None)
    req.portfolio.daily_realized_pnl_usd = Decimal("-600")
    assert review(req, now=now).decision == "APPROVE"


def test_stress_scenarios(now):
    scenarios = stress(sample_portfolio(now=now))
    assert len(scenarios["scenarios"]) == 4
    assert scenarios["current_gross_exposure_usd"] == "2500.00"
    assert Decimal(scenarios["scenarios"][1]["pnl_usd"]) == Decimal("-125")


@pytest.mark.parametrize("field,value", [
    ("quantity", "NaN"), ("quantity", "Infinity"), ("quantity", "0"),
    ("entry_price", "-1"), ("entry_price", "0"),
    ("symbol", "BTC/USDT"),
    ("venue", "IBKR_LIVE"),
    ("quote_as_of", "2026-01-01T00:00:00"),
])
def test_schema_rejects_invalid(now, field, value):
    with pytest.raises(ValidationError):
        request(now, **{field: value})


def test_portfolio_duplicate_positions_rejected(now):
    p = sample_portfolio(now=now).model_dump(mode="json")
    p["positions"].append(p["positions"][0])
    with pytest.raises(ValidationError):
        Portfolio.model_validate(p)


def test_policy_rejects_invalid_values():
    with pytest.raises(ValueError):
        RiskPolicy(max_risk_per_trade_pct=Decimal("NaN")).validate()
    with pytest.raises(ValueError):
        RiskPolicy(max_risk_per_trade_pct=Decimal("101")).validate()
