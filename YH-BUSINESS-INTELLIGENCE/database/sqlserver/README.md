# SQL Server setup

1. Run `00_create_database.sql` from `master`.
2. Point `DATABASE_URL` at the new database and run `alembic upgrade head` from `backend/`.
3. Run `01_seed_reference_data.sql`, then `02_integrity_and_tenant_security.sql` and `03_reporting_views.sql` against `YH_BusinessIntelligence`.
4. Run `python -m app.bootstrap` from `backend/` to create the first company, administrator, permissions, and starter accounts.

The SQLAlchemy model set is the migration source for the initial release. SQL Server adds posting triggers, row-level security, and reporting views through the scripts above. Tenant-scoped endpoints set `SESSION_CONTEXT('company_id')` only after checking the user's active membership.
