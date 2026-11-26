# Architecture

## Runtime shape

```text
React + TypeScript (browser) ─┐
                              ├── HTTPS / REST ── FastAPI ── SQLAlchemy ── SQL Server
Tauri 2 desktop WebView ──────┘                    │                  └── local SQLite for development
                                                   ├── financial and inventory workflows
                                                   ├── deterministic offline insight rules
                                                   └── warehouse fact refresh
```

The browser and desktop client share one frontend build and one API. The desktop package is a thin Windows WebView client; it contains no database credentials. A deployment can run the API beside SQL Server in a private network and serve the web client independently.

## Tenant boundary

Users are global identities. A `company_memberships` row grants access to one company; a membership receives one or more company-scoped roles. Every tenant API requires `X-Company-ID`, checks an active membership, then checks the permission required by that route. All business queries also filter by that company ID.

Relational constraints use company-qualified foreign keys for critical links such as journal lines to accounts and journal headers, invoice lines to products and warehouses, and bill lines to their company records. This prevents a row from a second company from being linked by mistake.

On SQL Server, after membership is confirmed the API sets the company in `SESSION_CONTEXT`. The optional RLS policy filters and blocks writes on tables carrying `company_id`. The session is cleared at the beginning of each API database session before user or membership checks, so a pooled connection cannot retain the previous request's tenant value.

## Accounting and currency

- Journal lines keep the source currency amount, source currency code, and the FX rate captured when the document is recorded.
- Each line also stores debit and credit translated into the company's functional currency. Those base amounts are the basis for balance validation and financial reports.
- For foreign currency, `functional_per_unit` means one unit of transaction currency multiplied by this rate yields the functional-currency amount.
- Rates are company-specific and effective-dated. If a request does not pass a rate, the API uses the most recent rate on or before the transaction date. No rate is fabricated when missing.
- A journal starts as a draft. Posting requires at least two lines and equality of total functional-currency debits and credits. The SQL Server trigger repeats the check at the database boundary.
- Posted journal headers and lines are immutable on SQL Server. The supported correction pattern is a separately recorded reversal and replacement.

## Business workflows

- Sales invoice draft: validates company customer, product, and warehouse; snapshots product unit cost and FX rate.
- Sales invoice post: checks stock for tracked products, writes receivable/revenue/tax/COGS/inventory journal lines, writes inventory issues, and marks the invoice posted in one transaction.
- Supplier bill draft: validates supplier, products, warehouses, currency, and FX rate.
- Supplier bill post: records the inventory/payables journal, receives stock, updates weighted average unit cost in functional currency, and marks the bill posted in one transaction.
- Expense post: records expense and payment-account journal lines and changes the expense to posted.
- Manual journal post: verifies the draft's translated balance before changing status.
- Stock movements: quantities are positive; movement type controls direction. Issue and outward-adjustment routes reject negative on-hand stock.

## Local analytics and warehouse

`app/api/routes.py` computes current KPIs from posted records only. `app/analytics` holds reusable local rule logic. No outbound model or analytics request is part of the app. The first warehouse slice is a financial fact at posted journal-line grain, with a conformed date dimension and functional-currency values. Refresh is idempotent by source journal line.

## Operational guidance

Keep migrations, API, and SQL Server security scripts in one controlled release. In production, disable automatic schema creation, use a dedicated SQL principal, terminate TLS at a trusted reverse proxy, set exact CORS origins, back up the database, and validate SQL Server RLS behavior using separate company users.
