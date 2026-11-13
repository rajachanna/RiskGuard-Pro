# RiskGuard Pro — Engineering Case Study

**Developer:** Raja Channa, NextGen Tech Solutions  
**Release:** v0.1 synthetic pre-trade risk review prototype  
**Demonstration:** `python scripts/showcase.py`

## The practical problem

Broker automation projects can connect alerts to order placement yet fail in less glamorous areas: stale prices, inconsistent account state, concentration, oversized orders, missing stops or an inability to explain why a strategy was blocked. The engineering goal is a separate, auditable approval boundary instead of scattering checks through every trading strategy.

**RiskGuard Pro provides explainable decisions without connecting to a broker.** Users send a hypothetical order and a synthetic portfolio. The engine returns `APPROVE`/`REJECT`, the result of every applicable rule, and a sizing estimate. The engine never calls order APIs.

## Implementation decisions

| Decision | Why | Limitation |
| --- | --- | --- |
| Pure function risk engine | Reproducible decisions and easy unit tests | Production needs deterministic snapshot provenance and risk reservation |
| `Decimal` arithmetic | Avoids most binary floating-point bookkeeping surprises | Does not solve contract size, tick size or currency conversion |
| Read-only synthetic portfolio | Avoids touching funded accounts | Not proof that a live account can be reconciled accurately |
| Expiry checks for quotes and marks | Demonstrates why stale state should fail closed | No authenticated market data provider |
| Policy separated from API | Makes thresholds inspectable and testable | Preset limits are illustrative, not suitable for all users |
| Audit history | Operators see decision and failed rule codes | SQLite is not an immutable external compliance ledger |
| Cash-only/long-only semantics | Reduces the domain complexity of demonstration | Does not evaluate futures, options, CFDs, Forex leverage or short sales |
| Emergency halt | A visible operator control | Halts approvals only; it does not cancel broker orders |

## Repeatable client demonstration

1. Submit a synthetic BTCUSDT BUY intent: 0.01 units at $65,000, stop $64,000, target $68,000. Stop-distance risk is $10, and reward/risk is 3.0.
2. Raise quantity above the order-notional limit. Observe `REJECT`, the failing code and the sizing estimate.
3. Change target to $65,100. The reward/risk requirement fails even if the other checks pass.
4. Flip the emergency halt control and confirm all reviews fail.
5. Run parallel -2%, -5%, -10% and -20% synthetic shocks and inspect the hypothetical loss, without claiming a forecast.
6. Inspect the SQLite audit history; only review metadata is stored.

All portfolio and price values are **invented demonstration values**, not exchange quotes or investment returns.

## Engineering scope needed for a real client

A production integration would need broker-confirmed positions and cash, contract specifications, funding/margin limits, fees, pending orders and fills, risk-capacity reservations, strong multi-user authorization, concurrent request handling, recovery after disconnections and independent acceptance tests in a paper/demo environment. These are *not* included in v0.1.

**Website:** https://nextgentechdev.com
