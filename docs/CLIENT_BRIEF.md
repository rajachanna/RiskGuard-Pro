# Custom Trading Risk Controls — Client Scoping Brief

RiskGuard Pro illustrates how to scope a separate risk-checking service for automated trading software. It **does not** have a real broker integration.

## Information needed from a client

| Question | Example |
| --- | --- |
| Trading environment | MT5 demo, IBKR paper, crypto exchange sandbox |
| Products / instruments | XAUUSD CFD, forex spot, stocks, crypto spot |
| Actual trade sizing units | MT5 lots, stock shares, crypto base units, contract sizes |
| Margin mode / leverage | Cross vs isolated, account multiplier, broker minimum margins |
| Risk policy | Max daily realized and unrealized loss, risk per trade, drawdown, symbol/sector exposure |
| Inputs | Account positions, market price source, stop/target signal, pending orders |
| Required action | Advisory review only, order blocking, or broker-side order routing |
| Success evidence | Broker-confirmed demo account, reject cases, reconciliation, exception reports |

## Suggested milestone structure

1. **Specifications and threat model:** exact account, symbols, risk rules, abnormal states and permission boundaries.
2. **Read-only data integration:** confirmed positions, balance and market data with timestamp verification.
3. **Risk decisions:** deterministic review service, reproducible tests, comprehensive reject reasons.
4. **Demonstration:** simulate stale data, network outages, limit breaches, partial fills and account mismatch.
5. **Optional execution integration:** a separately approved and tested broker paper/demo adapter.

Any proposed fees, guaranteed return or production safety claim should be based on real evidence rather than marketing language.

**Contact:** https://nextgentechdev.com
