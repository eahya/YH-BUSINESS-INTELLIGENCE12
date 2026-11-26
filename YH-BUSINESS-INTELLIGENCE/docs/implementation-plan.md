# Practical implementation plan

## Included in this initial runnable slice

- **Foundation:** SQLAlchemy model set, Alembic baseline, SQLite local mode, SQL Server setup scripts, JWT/Argon2 auth, company memberships, role permissions, audit records.
- **Accounting and FX:** chart of accounts seed, company FX rate maintenance, functional amount snapshots, balanced manual journal posting, trial balance, posted-journal immutability on SQL Server.
- **Operations:** customer/supplier/product/warehouse master data, one-line sales and purchase draft forms, posting with journal and stock changes, expense drafts/posts, inventory receipt/issue/adjustment.
- **Analytics:** posted-data KPIs, 6-month revenue trend, explainable local rules, date dimension, financial fact refresh.
- **Clients:** responsive English/Arabic React app and Tauri Windows shell.

## Next implementation increments

1. **Document completeness:** multi-line sales/purchase editor, credit notes/returns, payments/receipts, sales and purchase tax configuration, terms, due dates, document numbering, attachments.
2. **Accounting controls:** period locks, journal reversal UI and route, recurring journals, branch and cost-center dimensions, opening balances, bank reconciliation, AR/AP aging, retained earnings close.
3. **Inventory depth:** transfer workflow, cycle counts, serial/batch/expiry, valuation methods, COGS reconciliation, stock reservation, low-stock rules, complete integration with accounting adjustments.
4. **Tenant administration:** company/branch setup UI, membership lifecycle, password reset/rotation, optional MFA, invitation and role-change audit, session revocation.
5. **BI and warehouse:** additional date/company/product/customer/branch dimensions, sales/purchase/expense/inventory facts, incremental ETL checkpoints, query caching, exportable reports, margin and cohort analysis.
6. **Offline forecasting:** establish historical coverage and backtests first. Add a local, optional forecast package only after model error and hardware needs are measured; keep deterministic rule mode as the default.
7. **Release readiness:** market-specific tax/accounting review, SQL Server integration tests, backup/restore exercise, migration rehearsal, API load tests, observability, installer signing, and recovery documentation.

## Release gates

- A user from one company cannot read or mutate another company's documents through the API or SQL Server RLS.
- Every posted journal balances to the smallest supported functional unit and has at least two lines.
- Source and functional amounts reconcile using the captured FX rate.
- A sales post cannot issue more tracked stock than is available.
- An invoice or bill cannot be posted twice; all posting operations are atomic.
- Period reports reconcile to posted journal-line facts.
- Offline insights show their data basis and limitations and never call an external model.
- SQL Server scripts and migrations are tested against the actual supported server and ODBC driver versions.
