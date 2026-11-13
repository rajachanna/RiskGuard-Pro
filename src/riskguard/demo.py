"""Synthetic demo data generated at request time, never fetched from brokers."""
from datetime import datetime, timezone

from .models import Portfolio


def sample_portfolio(*, now: datetime | None = None) -> Portfolio:
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    return Portfolio.model_validate({
        "source": "SYNTHETIC",
        "equity_usd": "10000",
        "cash_usd": "7500",
        "peak_equity_usd": "10400",
        "daily_realized_pnl_usd": "-100",
        "as_of": timestamp,
        "positions": [
            {"venue": "PAPER_IBKR", "symbol": "AAPL", "quantity": "10",
             "mark_price": "175", "price_as_of": timestamp},
            {"venue": "PAPER_CEX", "symbol": "ETHUSDT", "quantity": "0.25",
             "mark_price": "3000", "price_as_of": timestamp},
        ],
    })
