# YH BUSINESS INTELLIGENCE

Hybrid Web + Windows Desktop business management and analytics foundation. One FastAPI service and one SQL Server database power both clients. The starter UI is bilingual (English/Arabic) and uses a dark charcoal and gold visual theme.

## What is included

- Multi-company users with company memberships, company creation, company roles, permission checks, JWT access tokens, and audit events.
- Company functional currencies, transaction-currency documents, dated FX rates, and stored functional-currency snapshots.
- Draft and posting workflows for sales invoices, supplier bills, expenses, journals, and inventory movements.
- Double-entry journal posting validation, SQL Server immutability and balance triggers, and tenant row-level security.
- Trial balance, revenue trend, period KPIs, deterministic offline insights, and an idempotent financial-fact warehouse refresh.
- React + TypeScript web client and a Tauri 2 Windows desktop shell.
- Backend tests covering tenant access, balanced posting, inventory, FX, profit reporting, local insights, and warehouse refresh.

This is a runnable product foundation. It is not a jurisdiction-specific accounting package: tax rules, statutory reports, payroll, bank reconciliation, period close, returns, and approval workflows need implementation for the target market before production use.

## Start locally (SQLite)

Python 3.11+ and Node.js 20+ are recommended. Run these commands from the repository root in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
python -m app.bootstrap
uvicorn app.main:app --reload
```

`app.bootstrap` asks for the company name, functional currency, administrator identity, and password. The password is entered through a hidden console prompt and must have at least 12 characters. The local default uses a SQLite file in `backend/yhbi.db` and creates the starter chart of accounts.

In a second terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the address Vite prints (normally `http://localhost:5173`). Sign in with the administrator created above. The API and OpenAPI reference run at `http://localhost:8000` and `http://localhost:8000/docs`.

## SQL Server setup

Use SQL Server 2019 or later, Microsoft ODBC Driver 18, and Python's `pyodbc` package. Set `DATABASE_URL` in `backend/.env`; encode reserved characters in the username/password and URL-encode spaces in the driver name.

```dotenv
DATABASE_URL=mssql+pyodbc://yhbi_user:CHANGE_ME@localhost:1433/YH_BusinessIntelligence?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=no
APP_ENV=production
AUTO_CREATE_SCHEMA=false
JWT_SECRET=replace-with-a-unique-random-value-of-at-least-32-bytes
CORS_ORIGINS=https://your-web-host.example,tauri.localhost
```

Run the SQL files in `database/sqlserver/README.md` in order. Apply the SQLAlchemy migration with `alembic upgrade head` from `backend/`. Use an administrative database principal for initial database creation/migration; the running API should use a separate SQL Server principal with only required data access. Do not commit `.env` files or passwords.

For a local SQL Server container, the root `docker-compose.yml` reads `MSSQL_SA_PASSWORD` from your shell and does not contain a saved password. SQL Server container images may require an explicit license acceptance and local disk space.

## Desktop app

The desktop executable is a Tauri client to the same API used by the web app; it does not embed SQL Server credentials. On Windows, install the Rust MSVC toolchain, Microsoft C++ Build Tools, and Microsoft Edge WebView2, then:

```powershell
cd frontend
npm install
npm run desktop:dev
npm run desktop:build
```

The production desktop client uses the `VITE_API_URL` value embedded at build time. Set it in `frontend/.env` to the API host that desktop users can reach. A reverse-proxy HTTPS endpoint is recommended for web and remote desktop clients.

## Tests and checks

```powershell
cd backend
pytest
```

```powershell
cd frontend
npm run build
```

The backend tests use an isolated in-memory SQLite database and do not need SQL Server. SQL Server row-level security and trigger scripts should additionally be exercised against the chosen SQL Server version before deployment.

## First-use workflow

1. Initialize a company and administrator with `python -m app.bootstrap`.
2. Sign in, create customers, suppliers, products, and warehouses in **Master data**.
3. Receive opening stock through **Inventory**; product unit cost is stored in the company functional currency.
4. For any foreign currency, add a dated FX rate in the API (`POST /api/v1/finance/fx-rates`) before recording documents. `functional_per_unit` means functional-currency units for one unit of the transaction currency.
5. Create sales invoices and purchase bills as drafts, then post them. Sales posting checks available inventory and records cost of goods sold; purchase posting receives stock and updates a weighted average product cost.
6. Record and post expenses. Draft manual journals can be posted only when the translated debit and credit totals balance.
7. Review trial balance, KPIs, insights, and refresh data-warehouse facts as needed.

## Configuration and deployment notes

- Authentication is email + password, using Argon2 password hashes and signed JWT access tokens. There is no public registration endpoint. Company administrators can create company workspaces, attach users, and create roles through `/api/v1/admin/*`.
- All tenant APIs require `X-Company-ID`; the API checks an active user membership before accessing tenant data. SQL Server requests then set `SESSION_CONTEXT('company_id')` for row-level security.
- The SQL Server scripts protect posted journal headers/lines from mutation. Corrections should be recorded as a new reversal journal; a self-service reversal endpoint is not yet included.
- The local intelligence engine is a versioned, deterministic rule set in Python. It sends no data to an LLM or external analytics API. It does not claim that a forecast is a certainty.
- Development `AUTO_CREATE_SCHEMA=true` is convenient for SQLite. Keep it false for SQL Server production and apply migrations deliberately.
- Use TLS, rotate `JWT_SECRET`, restrict SQL Server network access, configure backups and restore drills, and set the allowed CORS origins explicitly before deployment.

## Repository map

```text
backend/                 FastAPI, SQLAlchemy models, auth, business workflows, tests
frontend/                React/TypeScript browser app and Tauri desktop shell
database/migrations/     Alembic baseline migration
database/sqlserver/      Database, reference data, tenant security, and reporting SQL
docs/                    Architecture, data model, API, and implementation plan
```
