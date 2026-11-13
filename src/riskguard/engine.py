"""Pure deterministic risk checks. Returns decisions; DOES NOT transmit orders."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from .models import Portfolio, ReviewRequest, ReviewResult, Rule
from .policy import RiskPolicy

QTY_INCREMENT = Decimal("0.000001")  # Illustrative only; NOT exchange lot increments.


def _pct(value: Decimal, base: Decimal) -> Decimal:
    return value * Decimal("100") / base


def _age_seconds(then: datetime, now: datetime) -> Decimal:
    return Decimal(str((now - then).total_seconds()))


def _quantity_cap(amount: Decimal, price: Decimal) -> Decimal:
    return (max(Decimal("0"), amount) / price).quantize(QTY_INCREMENT, rounding=ROUND_DOWN)


def review(request: ReviewRequest, *, policy: RiskPolicy | None = None,
           now: datetime | None = None, halted: bool = False) -> ReviewResult:
    """Evaluate a long-only intent against a synthetic cash portfolio.

    This engine deliberately does not model options, futures, FX conversions,
    MT5 lot sizes, fees, margin, spreads, partial fills, or broker confirmations.
    No order is ever executed or recorded as a real fill.
    """
    rules: list[Rule] = []
    policy = policy or RiskPolicy()
    policy.validate()
    now = now or datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    order = request.intent
    account = request.portfolio
    equity = account.equity_usd
    value = order.quantity * order.entry_price
    risk_budget = equity * policy.max_risk_per_trade_pct / Decimal("100")
    max_daily_loss = equity * policy.max_daily_realized_loss_pct / Decimal("100")
    current_gross = sum((p.quantity * p.mark_price for p in account.positions), Decimal("0"))
    current_symbol = next((p for p in account.positions
                           if p.venue == order.venue and p.symbol == order.symbol), None)
    held_qty = current_symbol.quantity if current_symbol else Decimal("0")
    currently_held_value = held_qty * (current_symbol.mark_price if current_symbol else Decimal("0"))
    projected_symbol_value = (held_qty + order.quantity) * order.entry_price if order.side == "BUY" else (
        max(Decimal("0"), held_qty - order.quantity) * order.entry_price
    )
    projected_gross = current_gross - currently_held_value + projected_symbol_value
    dd_pct = _pct(account.peak_equity_usd - equity, account.peak_equity_usd)

    def add(code: str, passed: bool, msg: str):
        rules.append(Rule(code=code, passed=passed, message=msg))

    add("EMERGENCY_HALT", not halted, "Operator halt is active" if halted else "Routing review enabled")
    age = _age_seconds(order.quote_as_of, now)
    add("QUOTE_FRESHNESS", Decimal("-5") <= age <= policy.max_quote_age_seconds,
        f"Quote age: {age} seconds (maximum {policy.max_quote_age_seconds})")
    snapshot_age = _age_seconds(account.as_of, now)
    add("PORTFOLIO_FRESHNESS", Decimal("-5") <= snapshot_age <= policy.max_snapshot_age_seconds,
        f"Portfolio snapshot age: {snapshot_age} seconds")
    marks_ok = all(Decimal("-5") <= _age_seconds(p.price_as_of, now)
                   <= policy.max_position_mark_age_seconds for p in account.positions)
    add("POSITION_MARK_FRESHNESS", marks_ok,
        "All position marks are fresh" if marks_ok else "One or more position marks are stale")
    consistent = abs(account.cash_usd + current_gross - equity) <= Decimal("0.01")
    add("SYNTHETIC_RECONCILIATION", consistent,
        "Cash + synthetic marked holdings must match synthetic equity (USD, +/- $0.01)")
    add("DRAWDOWN_GUARD", dd_pct < policy.max_drawdown_pct or order.side == "SELL",
        f"Current drawdown: {dd_pct:.3f}% (buy limit: {policy.max_drawdown_pct}%)")
    add("DAILY_REALIZED_LOSS", account.daily_realized_pnl_usd > -max_daily_loss or order.side == "SELL",
        f"Simulated realized P&L: ${account.daily_realized_pnl_usd} (buy loss cap: ${max_daily_loss})")

    estimated_trade_risk = Decimal("0")
    rr = Decimal("0")
    suggested = None
    if order.side == "BUY":
        add("ORDER_NOTIONAL", value <= policy.max_order_notional_usd,
            f"Requested ${value} (limit ${policy.max_order_notional_usd})")
        add("CASH_AVAILABLE", value <= account.cash_usd,
            f"Cash ${account.cash_usd} vs requested ${value}")
        max_symbol = equity * policy.max_symbol_exposure_pct / Decimal("100")
        max_gross = equity * policy.max_gross_exposure_pct / Decimal("100")
        add("SYMBOL_EXPOSURE", projected_symbol_value <= max_symbol,
            f"Projected symbol exposure ${projected_symbol_value} (limit ${max_symbol})")
        add("GROSS_EXPOSURE", projected_gross <= max_gross,
            f"Projected gross exposure ${projected_gross} (limit ${max_gross})")
        open_positions = len(account.positions) + (0 if current_symbol else 1)
        add("POSITION_COUNT", open_positions <= policy.max_open_positions,
            f"Projected open position count {open_positions} (limit {policy.max_open_positions})")
        valid_stop = order.stop_price is not None and order.stop_price < order.entry_price
        valid_target = order.target_price is not None and order.target_price > order.entry_price
        add("PROTECTIVE_STOP", valid_stop, "BUY requires a stop strictly below entry")
        add("PROFIT_TARGET", valid_target, "BUY requires a target strictly above entry")
        if valid_stop:
            distance = order.entry_price - order.stop_price
            estimated_trade_risk = distance * order.quantity
            add("RISK_PER_TRADE", estimated_trade_risk <= risk_budget,
                f"Proposed stop-distance risk ${estimated_trade_risk} (limit ${risk_budget})")
            if valid_target:
                rr = (order.target_price - order.entry_price) / distance
                add("REWARD_RISK", rr >= policy.min_reward_risk_ratio,
                    f"Proposed reward/risk {rr:.3f} (minimum {policy.min_reward_risk_ratio})")
            candidates = [
                _quantity_cap(risk_budget, distance),
                _quantity_cap(account.cash_usd, order.entry_price),
                _quantity_cap(policy.max_order_notional_usd, order.entry_price),
                _quantity_cap(max_symbol - held_qty * order.entry_price, order.entry_price),
                _quantity_cap(max_gross - (current_gross - currently_held_value)
                              - held_qty * order.entry_price, order.entry_price),
            ]
            suggested = str(max(Decimal("0"), min(candidates)))
    else:
        add("LONG_ONLY_REDUCTION", current_symbol is not None and order.quantity <= held_qty,
            f"Sell quantity {order.quantity} must not exceed same-venue holdings {held_qty}")
        # A risk-reducing sell has no mandatory stop/target. This preview never places it.

    metrics = {
        "equity_usd": str(equity),
        "cash_usd": str(account.cash_usd),
        "order_notional_usd": str(value),
        "estimated_stop_risk_usd": str(estimated_trade_risk),
        "risk_budget_usd": str(risk_budget),
        "reward_risk_ratio": str(rr),
        "current_gross_exposure_usd": str(current_gross),
        "projected_gross_exposure_usd": str(projected_gross),
        "projected_symbol_exposure_usd": str(projected_symbol_value),
        "drawdown_pct": str(dd_pct),
        "daily_realized_pnl_usd": str(account.daily_realized_pnl_usd),
    }
    return ReviewResult(
        decision="APPROVE" if all(rule.passed for rule in rules) else "REJECT",
        rules=rules, metrics=metrics,
        max_suggested_buy_quantity=suggested,
    )


def stress(portfolio: Portfolio, *, shocks_pct: tuple[int, ...] = (-2, -5, -10, -20)) -> dict:
    """One-factor illustrative parallel long-only mark shock, not VaR or forecast."""
    gross = sum((p.quantity * p.mark_price for p in portfolio.positions), Decimal("0"))
    scenarios = []
    for shock in shocks_pct:
        if shock < -100 or shock > 100:
            raise ValueError("Shock percent must be between -100 and 100")
        pnl = gross * Decimal(shock) / Decimal("100")
        new_equity = portfolio.equity_usd + pnl
        scenarios.append({"shock_pct": str(shock), "pnl_usd": str(pnl),
                          "projected_equity_usd": str(new_equity)})
    return {
        "mode": "SYNTHETIC_STRESS_ONLY",
        "current_gross_exposure_usd": str(gross),
        "scenarios": scenarios,
        "caveat": "Assumes every asset changes by the same percentage; excludes liquidity, fees, correlations and leverage.",
    }
