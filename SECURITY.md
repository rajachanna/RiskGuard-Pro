# Security and safety boundaries

**RiskGuard Pro is an experimental local-only, review-only portfolio project.** It must never be used as a funded-account risk safeguard.

- Store the operator key outside source control and do not paste private keys or broker credentials in chats or issues. The app rejects missing, short and placeholder `RG_OPERATOR_KEY` values.
- The dashboard serves without auth, but every portfolio, policy, review and audit API endpoint requires the operator key. The key is held only in the browser's page memory, not localStorage.
- Docker publishes localhost only. Do not expose this application on the public internet without TLS, session management, proper authentication, CORS/CSRF review, request size/rate limits and an independent security review.
- The prototype accepts a **caller-provided synthetic portfolio**. Its contents can be manipulated; all approvals are advisory and unsuitable for broker order execution.
- No real order, broker connection, live market request or external payment is made.
- An operator halt prevents an `APPROVE` review, not broker execution or liquidation.
- Audit entries include venue, symbol, action, decision and failed rule codes only; there is no immutable compliance log.
- SQLite demo state is single-host and does not reserve risk capacity atomically across distributed trading services. A real product requires transaction-safe exposure reservation and broker reconciliation.
- The model intentionally excludes derivative contracts, leverage, lot sizes, exchange tick sizes, fees, spreads and slippage. Do not rely on suggested unit sizing for any broker.
- All stress scenarios are hypothetical single-factor moves, not Value-at-Risk or reliable future losses.

For privately reporting issues, contact https://nextgentechdev.com.
