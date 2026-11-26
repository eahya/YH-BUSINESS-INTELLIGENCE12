# API guide

Interactive OpenAPI docs: `http://localhost:8000/docs`.

## Authentication and tenant header

1. `POST /api/v1/auth/token` with `{"email":"...","password":"..."}` returns a bearer access token.
2. `GET /api/v1/companies` lists the companies where the user has an active membership.
3. Send `Authorization: Bearer <token>` and `X-Company-ID: <company id>` to every tenant-scoped endpoint.
4. A missing membership returns `403`; the API does not accept a client-supplied company ID without a membership check.

## Routes

| Area | Routes |
|---|---|
| Auth | `POST /auth/token`, `GET /auth/me`, `GET /companies` |
| Currencies | `GET /currencies` |
| Company master data | `GET/POST /customers`, `/suppliers`, `/products`, `/warehouses` |
| Companies, users, and roles | `POST /admin/companies`, `GET/POST /admin/users`, `GET/POST /admin/roles` |
| Accounting | `GET/POST /finance/accounts`, `GET/POST /finance/fx-rates`, `GET/POST /finance/journals`, `GET /finance/journals/{id}/lines`, `POST /finance/journals/{id}/post`, `GET /finance/trial-balance` |
| Expenses | `GET/POST /expenses`, `POST /expenses/{id}/post` |
| Sales | `GET/POST /sales/invoices`, `POST /sales/invoices/{id}/post` |
| Purchasing | `GET/POST /purchases/bills`, `POST /purchases/bills/{id}/post` |
| Inventory | `GET /inventory/balances`, `POST /inventory/movements` |
| Analytics | `GET /analytics/overview`, `GET /analytics/revenue-trend`, `GET /analytics/insights`, `POST /analytics/warehouse/refresh` |
| Audit | `GET /audit/events` |

`GET /api/v1/health` is a liveness check. The overview accepts `start` and `end` ISO dates; other date-filtered lists accept the same query parameters. The insight response includes `engine: local-rules-v1` and `external_llm: false`.

## FX rate request

```json
{
  "currency_code": "EUR",
  "rate_date": "2025-02-01",
  "functional_per_unit": "1.08",
  "source": "MANUAL"
}
```

Functional currency is implicit and always rate 1. A foreign-currency document can provide an explicit positive rate or uses the latest configured rate on or before its date. The rate is copied into the transaction when the draft is created.

## Draft and post

Create invoice, supplier bill, expense, or journal first, review it, then call its `/post` route. Posting is one transaction: either the document, ledger, and stock changes all commit, or they all roll back. A posted journal cannot be modified through the API, and the SQL Server triggers also reject direct edits. Record a new reversal journal for corrections.

## Role permissions

Company administrators created at bootstrap can create another company workspace (the creator is attached as that company's administrator), attach existing accounts or create users with a company role, and create roles from these permission codes:

`masterdata.read`, `masterdata.write`, `finance.read`, `finance.write`, `sales.read`, `sales.write`, `purchases.read`, `purchases.write`, `inventory.read`, `inventory.write`, `analytics.read`, `warehouse.refresh`, `security.manage`.

User creation accepts a temporary password directly; communicate it through an approved secure channel and require a password reset workflow before broad use. Password-reset and invitation-email delivery are not implemented in this starter.
