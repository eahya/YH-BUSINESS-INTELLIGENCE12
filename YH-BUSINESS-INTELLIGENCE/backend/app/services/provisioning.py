from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Account, Company, CompanyMembership, Currency, MembershipRole, Permission, Role, RolePermission, User

CURRENCIES = {
    "AED": "UAE Dirham", "AUD": "Australian Dollar", "CAD": "Canadian Dollar",
    "EGP": "Egyptian Pound", "EUR": "Euro", "GBP": "Pound Sterling",
    "JPY": "Japanese Yen", "SAR": "Saudi Riyal", "USD": "US Dollar",
}
PERMISSIONS = {
    "masterdata.read": "Read company master data", "masterdata.write": "Manage company master data",
    "finance.read": "Read accounting and finance", "finance.write": "Manage accounting and finance",
    "sales.read": "Read sales documents", "sales.write": "Create and post sales documents",
    "purchases.read": "Read purchase documents", "purchases.write": "Create and post purchase documents",
    "inventory.read": "Read inventory", "inventory.write": "Manage stock movements",
    "analytics.read": "Read reports and local insights", "warehouse.refresh": "Refresh data warehouse facts",
    "security.manage": "Manage company users and roles",
}
ACCOUNT_SEED = [
    ("1000", "Cash and bank", "ASSET"), ("1100", "Trade receivables", "ASSET"),
    ("1300", "Inventory", "ASSET"), ("2000", "Trade payables", "LIABILITY"),
    ("2100", "Sales tax payable", "LIABILITY"), ("3000", "Retained earnings", "EQUITY"),
    ("4000", "Sales revenue", "REVENUE"), ("5000", "Cost of goods sold", "EXPENSE"),
    ("6000", "Operating expenses", "EXPENSE"),
]


def seed_reference_data(db: Session) -> None:
    for code, name in CURRENCIES.items():
        if not db.get(Currency, code):
            db.add(Currency(code=code, name=name, minor_units=0 if code == "JPY" else 2))
    for code, description in PERMISSIONS.items():
        if not db.get(Permission, code):
            db.add(Permission(code=code, description=description))
    db.flush()


def set_sqlserver_company_context(db: Session, company_id: int) -> None:
    if db.get_bind().dialect.name == "mssql":
        db.execute(text("EXEC sys.sp_set_session_context @key=N'company_id', @value=:company_id"),
                   {"company_id": company_id})


def provision_company_defaults(db: Session, company: Company, admin: User) -> None:
    """Attach the administrator, company-scoped admin role, permissions, and starter COA."""
    set_sqlserver_company_context(db, company.id)
    membership = CompanyMembership(company_id=company.id, user_id=admin.id, is_active=True)
    db.add(membership)
    role = Role(company_id=company.id, code="ADMIN", name="Administrator")
    db.add(role)
    db.flush()
    db.add(MembershipRole(company_id=company.id, membership_id=membership.id, role_id=role.id))
    for permission in db.scalars(select(Permission)).all():
        db.add(RolePermission(company_id=company.id, role_id=role.id, permission_code=permission.code))
    for code, name, account_type in ACCOUNT_SEED:
        db.add(Account(company_id=company.id, code=code, name=name, account_type=account_type))
