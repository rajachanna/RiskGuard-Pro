# Roadmap — RiskGuard Pro

## v0.1 — implemented

- Explicit Pydantic order, snapshot and position contracts
- Deterministic explainable BUY/SELL risk reviews
- Pre-trade checks for cash, risk budget, stop/target, ratio, exposure, drawdown, daily realized loss, timestamp freshness and operator halt
- Synthetic USD mark-to-market consistency check
- Portfolio stress table and local dashboard
- SQLite decision audit and API key authentication
- Unit/integration tests and offline demonstration script

## v0.2 — proposed

- Injectable market data/portfolio snapshot provider interfaces
- Improved policy versioning and change audit
- More sophisticated price-source freshness and risk-capacity reservation
- Configurable lot steps and broker-native instrument metadata
- Better stress modelling, stress attribution and counterparty exposure
- Load testing and database migration strategy

## v0.3 — proposed (only after approval and proper account access)

- Verified read-only MT5 demo and IBKR paper accounts, then separately scoped broker adapters
- Broker-confirmed position reconciliation, pending order tracking and partial fill support
- Operational recovery, alerts, rate limiting, secrets management and HTTPS deployment

**No live execution, guaranteed profit, production risk protection or actual brokerage account integration is implemented.**
