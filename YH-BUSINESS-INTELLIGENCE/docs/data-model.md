# Data model and accounting notes

The initial SQLAlchemy/Alembic baseline creates these logical groups in the default `dbo` schema. All monetary columns use `DECIMAL(19,4)`; FX rates use `DECIMAL(19,8)`.

| Area | Main records | Purpose |
|---|---|---|
| Identity | `users`, `company_memberships`, `roles`, `permissions`, `membership_roles`, `role_permissions` | One login can access several companies with company-specific permissions. |
| Company setup | `companies`, `currencies`, `fx_rates` | Functional currency and effective-dated company exchange rates. |
| Master data | `customers`, `suppliers`, `products`, `warehouses`, `accounts` | Company-scoped operational and ledger records. |
| Finance | `journal_entries`, `journal_lines`, `expenses` | Draft/posted double-entry ledger and expenses. |
| Sales | `sales_invoices`, `sales_invoice_lines` | Customer invoices with source and functional-currency snapshots. |
| Purchasing | `purchase_bills`, `purchase_bill_lines` | Supplier invoices and inventory receipts. |
| Inventory | `stock_movements` | Immutable quantity movements; current stock is their signed sum. |
| Audit | `audit_events` | Company-scoped record of key creates and posts. |
| Analytics | `dim_date`, `fact_financial_transactions` | First star-schema dimension and posted journal-line fact. |

## Functional-currency formula

If a company reports in USD and records 100 EUR at `functional_per_unit = 1.08`, the functional amount is `100 × 1.08 = USD 108.00`. The transaction record retains EUR 100 and rate 1.08; the ledger line retains EUR debit/credit plus USD base debit/credit. Revaluation of open balances is not implemented yet.

## Journal example

For a sale of 2 units at 10 each with 4 tax and a functional unit cost of 5:

| Account | Debit (functional) | Credit (functional) |
|---|---:|---:|
| Trade receivables | 24 | 0 |
| Sales revenue | 0 | 20 |
| Sales tax payable | 0 | 4 |
| Cost of goods sold | 10 | 0 |
| Inventory | 0 | 10 |
| **Total** | **34** | **34** |

Sales revenue excludes tax. The overview's net profit estimate is posted revenue minus posted cost of goods sold minus posted expenses for the requested dates. It does not replace a statutory profit-and-loss statement or tax filing.

## Migration ownership

`database/migrations/versions/0001_initial.py` uses the frozen ORM snapshot in `database/migrations/schema_v1.py`. Keep both files unchanged after release and add a later explicit revision for every schema change. The supplemental SQL Server scripts add features not portable across SQLite and SQL Server: posting triggers, row-level security, and reporting views.
