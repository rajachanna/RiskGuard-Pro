"""Explicit and immutable risk policy. Values are illustrative, not advice."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RiskPolicy:
    max_risk_per_trade_pct: Decimal = Decimal("1.0")
    min_reward_risk_ratio: Decimal = Decimal("1.5")
    max_order_notional_usd: Decimal = Decimal("2500")
    max_symbol_exposure_pct: Decimal = Decimal("25")
    max_gross_exposure_pct: Decimal = Decimal("80")
    max_daily_realized_loss_pct: Decimal = Decimal("3")
    max_drawdown_pct: Decimal = Decimal("10")
    max_open_positions: int = 8
    max_quote_age_seconds: int = 60
    max_snapshot_age_seconds: int = 120
    max_position_mark_age_seconds: int = 120

    def validate(self) -> None:
        values = [self.max_risk_per_trade_pct, self.min_reward_risk_ratio,
                  self.max_order_notional_usd, self.max_symbol_exposure_pct,
                  self.max_gross_exposure_pct, self.max_daily_realized_loss_pct,
                  self.max_drawdown_pct]
        if any(not value.is_finite() or value <= 0 for value in values):
            raise ValueError("All risk policy values must be positive and finite")
        for fraction in (self.max_risk_per_trade_pct, self.max_symbol_exposure_pct,
                         self.max_gross_exposure_pct, self.max_daily_realized_loss_pct,
                         self.max_drawdown_pct):
            if fraction > 100:
                raise ValueError("Percentage policy cannot exceed 100")
        if min(self.max_open_positions, self.max_quote_age_seconds,
               self.max_snapshot_age_seconds, self.max_position_mark_age_seconds) <= 0:
            raise ValueError("Counts and freshness limits must be positive")

    def as_dict(self) -> dict[str, str | int]:
        return {k: str(v) if isinstance(v, Decimal) else v for k, v in vars(self).items()}
