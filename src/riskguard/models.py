"""Typed, validated contracts for a cash-only / long-only risk review.

All currency amounts are fictional USD; input quantities are asset units,
NOT broker contracts, MT5 lots, or margin/leverage-adjusted amounts.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def finite_positive(value: Decimal) -> Decimal:
    if not value.is_finite() or value <= 0:
        raise ValueError("Value must be a finite positive number")
    return value


def finite_nonnegative(value: Decimal) -> Decimal:
    if not value.is_finite() or value < 0:
        raise ValueError("Value must be a finite non-negative number")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(StrictModel):
    venue: Literal["PAPER_IBKR", "PAPER_MT5", "PAPER_CEX"]
    symbol: str = Field(min_length=2, max_length=22, pattern=r"^[A-Za-z0-9._-]+$")
    quantity: Decimal
    mark_price: Decimal
    price_as_of: datetime

    @field_validator("quantity", "mark_price")
    @classmethod
    def valid_positive(cls, value: Decimal) -> Decimal:
        return finite_positive(value)

    @field_validator("symbol")
    @classmethod
    def normalized_symbol(cls, value: str) -> str:
        return value.upper()

    @field_validator("price_as_of")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone offset")
        return value


class Portfolio(StrictModel):
    source: Literal["SYNTHETIC"] = "SYNTHETIC"
    equity_usd: Decimal
    cash_usd: Decimal
    peak_equity_usd: Decimal
    daily_realized_pnl_usd: Decimal
    as_of: datetime
    positions: list[Position]

    @field_validator("equity_usd", "peak_equity_usd")
    @classmethod
    def positive_balance(cls, value: Decimal) -> Decimal:
        return finite_positive(value)

    @field_validator("cash_usd")
    @classmethod
    def cash_nonnegative(cls, value: Decimal) -> Decimal:
        return finite_nonnegative(value)

    @field_validator("daily_realized_pnl_usd")
    @classmethod
    def pnl_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Daily realized P&L must be finite")
        return value

    @field_validator("as_of")
    @classmethod
    def aware_date(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Portfolio timestamp must include timezone")
        return value

    @model_validator(mode="after")
    def unique_positions(self):
        identities = {(p.venue, p.symbol) for p in self.positions}
        if len(identities) != len(self.positions):
            raise ValueError("Duplicate venue/symbol positions are unsupported")
        if self.peak_equity_usd < self.equity_usd:
            raise ValueError("Peak equity cannot be below current equity")
        return self


class OrderIntent(StrictModel):
    venue: Literal["PAPER_IBKR", "PAPER_MT5", "PAPER_CEX"]
    symbol: str = Field(min_length=2, max_length=22, pattern=r"^[A-Za-z0-9._-]+$")
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    entry_price: Decimal
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    quote_as_of: datetime

    @field_validator("symbol")
    @classmethod
    def normalized_symbol(cls, value: str) -> str:
        return value.upper()

    @field_validator("quantity", "entry_price")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        return finite_positive(value)

    @field_validator("stop_price", "target_price")
    @classmethod
    def positive_optional(cls, value: Decimal | None) -> Decimal | None:
        return finite_positive(value) if value is not None else value

    @field_validator("quote_as_of")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Quote timestamp requires timezone")
        return value


class ReviewRequest(StrictModel):
    intent: OrderIntent
    portfolio: Portfolio


class Rule(StrictModel):
    code: str
    passed: bool
    message: str


class ReviewResult(StrictModel):
    decision: Literal["APPROVE", "REJECT"]
    mode: Literal["REVIEW_ONLY"] = "REVIEW_ONLY"
    order_executed: Literal[False] = False
    rules: list[Rule]
    metrics: dict[str, str]
    max_suggested_buy_quantity: str | None = None
