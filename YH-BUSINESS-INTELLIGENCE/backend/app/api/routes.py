from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.analytics.rules import insights_for_overview
from app.models import (
    Account, AuditEvent, Company, CompanyMembership, Currency, Customer, Expense, FactFinancialTransaction,
    FxRate, JournalEntry, JournalLine, MembershipRole, Permission, Product, PurchaseBill,
    PurchaseBillLine, Role, SalesInvoice, SalesInvoiceLine, StockMovement, Supplier, User,
    RolePermission, Warehouse, DimDate,
)
from app.schemas import (
    AccountCreate, AccountOut, CompanyOut, CustomerCreate, CustomerOut, ExpenseCreate, ExpenseOut,
    FxRateCreate, FxRateOut, JournalCreate, JournalOut, OverviewOut, ProductCreate, ProductOut,
    PurchaseBillCreate, PurchaseBillOut, SalesInvoiceCreate, SalesInvoiceOut, StockMovementCreate,
    StockMovementOut, SupplierCreate, SupplierOut, TokenRequest, TokenResponse, UserOut,
    WarehouseCreate, WarehouseOut, RoleCreate, RoleOut, UserInviteCreate, CompanyCreate,
)
from app.security import create_access_token, get_current_user, require_permission, verify_password, hash_password
from app.services.provisioning import provision_company_defaults

router = APIRouter(prefix="/api/v1")
MONEY_QUANTUM = Decimal("0.0001")
ZERO = Decimal("0")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def audit(db: Session, company_id: int, user_id: int | None, action: str,
          entity_type: str, entity_id: int | str, details: str | None = None) -> None:
    db.add(AuditEvent(company_id=company_id, user_id=user_id, action=action,
                      entity_type=entity_type, entity_id=str(entity_id), details=details))


def company_row(db: Session, company_id: int) -> Company:
    company = db.get(Company, company_id)
    if not company or not company.is_active:
        raise HTTPException(404, "Company not found")
    return company


def fx_rate(db: Session, company_id: int, currency_code: str, on_date: date,
            supplied: Decimal | None = None) -> Decimal:
    company = company_row(db, company_id)
    code = currency_code.upper()
    if not db.get(Currency, code):
        raise HTTPException(422, f"Currency {code} is not configured")
    if code == company.functional_currency_code:
        if supplied is not None and supplied != Decimal("1"):
            raise HTTPException(422, "Functional-currency exchange rate must equal 1")
        return Decimal("1")
    if supplied is not None:
        return supplied
    rate = db.scalar(
        select(FxRate.functional_per_unit)
        .where(FxRate.company_id == company_id, FxRate.currency_code == code, FxRate.rate_date <= on_date)
        .order_by(FxRate.rate_date.desc())
        .limit(1)
    )
    if rate is None:
        raise HTTPException(422, f"No {code} FX rate exists on or before {on_date}; add a rate first")
    return Decimal(rate)


def account_by_code(db: Session, company_id: int, code: str) -> Account:
    account = db.scalar(select(Account).where(Account.company_id == company_id, Account.code == code,
                                             Account.is_active.is_(True)))
    if not account:
        raise HTTPException(422, f"Required active account {code} is missing from the chart of accounts")
    return account


def add_journal_line(db: Session, entry: JournalEntry, account: Account, currency_code: str,
                     rate: Decimal, debit: Decimal, credit: Decimal, description: str) -> None:
    db.add(JournalLine(
        company_id=entry.company_id, journal_id=entry.id, account_id=account.id,
        currency_code=currency_code, exchange_rate=rate, debit=debit, credit=credit,
        base_debit=money(debit * rate), base_credit=money(credit * rate), description=description,
    ))


def create_system_journal(db: Session, company_id: int, user_id: int, number: str,
                          on_date: date, description: str, lines: list[tuple[Account, str, Decimal,
                          Decimal, Decimal, str]], source_type: str, source_id: int) -> JournalEntry:
    entry = JournalEntry(company_id=company_id, journal_number=number, journal_date=on_date,
                         description=description, source_type=source_type, source_id=str(source_id),
                         status="DRAFT", created_by=user_id)
    db.add(entry)
    db.flush()
    for account, currency_code, rate, debit, credit, memo in lines:
        add_journal_line(db, entry, account, currency_code, rate, debit, credit, memo)
    db.flush()
    totals = db.execute(
        select(func.sum(JournalLine.base_debit), func.sum(JournalLine.base_credit))
        .where(JournalLine.company_id == company_id, JournalLine.journal_id == entry.id)
    ).one()
    if money(Decimal(totals[0] or 0)) != money(Decimal(totals[1] or 0)):
        raise HTTPException(422, "Generated journal is out of balance in functional currency")
    entry.status = "POSTED"
    entry.posted_at = datetime.now(UTC)
    db.flush()
    return entry


def stock_signed(movement_type: str):
    return case(
        (StockMovement.movement_type.in_(["RECEIPT", "ADJUSTMENT_IN"]), StockMovement.quantity),
        else_=-StockMovement.quantity,
    )


def stock_value_signed():
    amount = StockMovement.quantity * StockMovement.unit_cost
    return case(
        (StockMovement.movement_type.in_(["RECEIPT", "ADJUSTMENT_IN"]), amount),
        else_=-amount,
    )


def stock_position(db: Session, company_id: int, product_id: int,
                   warehouse_id: int | None = None) -> tuple[Decimal, Decimal]:
    stmt = select(StockMovement.movement_type, StockMovement.quantity, StockMovement.unit_cost).where(
        StockMovement.company_id == company_id, StockMovement.product_id == product_id)
    if warehouse_id is not None:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    rows = db.execute(stmt).all()
    units = ZERO
    value = ZERO
    for kind, quantity, unit_cost in rows:
        quantity, unit_cost = Decimal(quantity), Decimal(unit_cost)
        direction = Decimal("1") if kind in {"RECEIPT", "ADJUSTMENT_IN"} else Decimal("-1")
        units += direction * quantity
        value += direction * quantity * unit_cost
    return units, value


def lock_product_stock(db: Session, company_id: int, product_id: int) -> None:
    """Serialize stock-affecting writes by product on SQL Server until commit/rollback."""
    if db.get_bind().dialect.name == "mssql":
        db.execute(text("SELECT id FROM dbo.products WITH (UPDLOCK, HOLDLOCK) "
                        "WHERE company_id=:company_id AND id=:product_id"),
                   {"company_id": company_id, "product_id": product_id}).first()


def lock_scoped_row(db: Session, table: str, company_id: int, row_id: int) -> None:
    if table not in {"journal_entries", "expenses", "sales_invoices", "purchase_bills"}:
        raise ValueError("Unsupported lock target")
    if db.get_bind().dialect.name == "mssql":
        db.execute(text(f"SELECT id FROM dbo.{table} WITH (UPDLOCK, HOLDLOCK) "
                        "WHERE company_id=:company_id AND id=:row_id"),
                   {"company_id": company_id, "row_id": row_id}).first()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "yh-business-intelligence-api"}


@router.post("/auth/token", response_model=TokenResponse)
def login(payload: TokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    from app.config import get_settings
    settings = get_settings()
    return TokenResponse(access_token=create_access_token(user.id), expires_in=settings.access_token_minutes * 60)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/admin/users")
def list_company_users(context=Depends(require_permission("security.manage")), db: Session = Depends(get_db)):
    _, company_id = context
    rows = db.execute(select(User.id, User.email, User.full_name, User.is_active, Role.code.label("role_code"))
        .join(CompanyMembership, CompanyMembership.user_id == User.id)
        .join(MembershipRole, (MembershipRole.membership_id == CompanyMembership.id) &
              (MembershipRole.company_id == CompanyMembership.company_id))
        .join(Role, (Role.id == MembershipRole.role_id) & (Role.company_id == MembershipRole.company_id))
        .where(CompanyMembership.company_id == company_id, CompanyMembership.is_active.is_(True))
        .order_by(User.full_name)).all()
    return [{"id": row.id, "email": row.email, "full_name": row.full_name,
             "is_active": row.is_active, "role_code": row.role_code} for row in rows]


@router.post("/admin/users", status_code=201)
def add_company_user(payload: UserInviteCreate,
                     context=Depends(require_permission("security.manage")), db: Session = Depends(get_db)):
    actor, company_id = context
    email = payload.email.lower()
    role = db.scalar(select(Role).where(Role.company_id == company_id, Role.code == payload.role_code.upper()))
    if not role:
        raise HTTPException(422, "Role does not exist in this company")
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user:
        current_membership = db.scalar(select(CompanyMembership.id).where(
            CompanyMembership.company_id == company_id, CompanyMembership.user_id == user.id))
        if current_membership:
            raise HTTPException(409, "This user already belongs to the selected company")
    else:
        if not payload.temporary_password:
            raise HTTPException(422, "A 12-character temporary password is required for a new user")
        user = User(email=email, full_name=payload.full_name,
                    password_hash=hash_password(payload.temporary_password))
        db.add(user)
        db.flush()
    membership = CompanyMembership(company_id=company_id, user_id=user.id, is_active=True)
    db.add(membership)
    db.flush()
    db.add(MembershipRole(company_id=company_id, membership_id=membership.id, role_id=role.id))
    audit(db, company_id, actor.id, "CREATE", "UserMembership", membership.id, role.code)
    db.commit()
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role_code": role.code}


@router.get("/admin/roles", response_model=list[RoleOut])
def list_company_roles(context=Depends(require_permission("security.manage")), db: Session = Depends(get_db)):
    _, company_id = context
    roles = db.scalars(select(Role).where(Role.company_id == company_id).order_by(Role.code)).all()
    result = []
    for role in roles:
        codes = db.scalars(select(RolePermission.permission_code).where(
            RolePermission.company_id == company_id, RolePermission.role_id == role.id).order_by(
                RolePermission.permission_code)).all()
        result.append(RoleOut(code=role.code, name=role.name, permission_codes=list(codes)))
    return result


@router.post("/admin/roles", response_model=RoleOut, status_code=201)
def create_company_role(payload: RoleCreate,
                        context=Depends(require_permission("security.manage")), db: Session = Depends(get_db)):
    actor, company_id = context
    code = payload.code.upper().replace(" ", "_")
    permissions = set(db.scalars(select(Permission.code).where(Permission.code.in_(payload.permission_codes))).all())
    requested = set(payload.permission_codes)
    if permissions != requested:
        raise HTTPException(422, f"Unknown permissions: {', '.join(sorted(requested - permissions))}")
    role = Role(company_id=company_id, code=code, name=payload.name)
    db.add(role)
    db.flush()
    for permission_code in sorted(permissions):
        db.add(RolePermission(company_id=company_id, role_id=role.id, permission_code=permission_code))
    audit(db, company_id, actor.id, "CREATE", "Role", role.id, code)
    db.commit()
    return RoleOut(code=code, name=payload.name, permission_codes=sorted(permissions))


@router.get("/companies", response_model=list[CompanyOut])
def companies(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Company]:
    return list(db.scalars(
        select(Company).join(CompanyMembership, CompanyMembership.company_id == Company.id)
        .where(CompanyMembership.user_id == user.id, CompanyMembership.is_active.is_(True), Company.is_active.is_(True))
        .order_by(Company.name)
    ).all())


@router.post("/admin/companies", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyCreate,
                   context=Depends(require_permission("security.manage")), db: Session = Depends(get_db)):
    actor, _current_company_id = context
    if not db.get(Currency, payload.functional_currency_code):
        raise HTTPException(422, f"Unsupported functional currency {payload.functional_currency_code}")
    company = Company(name=payload.name.strip(),
        functional_currency_code=payload.functional_currency_code,
        country_code=payload.country_code)
    if not company.name:
        raise HTTPException(422, "Company name cannot be blank")
    db.add(company)
    db.flush()
    provision_company_defaults(db, company, actor)
    audit(db, company.id, actor.id, "CREATE", "Company", company.id, "Company workspace created")
    db.commit()
    db.refresh(company)
    return company


@router.get("/currencies")
def currencies(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    rows = db.scalars(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.code)).all()
    return [{"code": row.code, "name": row.name, "minor_units": row.minor_units} for row in rows]


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(context=Depends(require_permission("masterdata.read")), db: Session = Depends(get_db)):
    _, company_id = context
    return list(db.scalars(select(Customer).where(Customer.company_id == company_id).order_by(Customer.name)).all())


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, context=Depends(require_permission("masterdata.write")),
                    db: Session = Depends(get_db)):
    user, company_id = context
    row = Customer(company_id=company_id, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "Customer", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(context=Depends(require_permission("masterdata.read")), db: Session = Depends(get_db)):
    _, company_id = context
    return list(db.scalars(select(Supplier).where(Supplier.company_id == company_id).order_by(Supplier.name)).all())


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(payload: SupplierCreate, context=Depends(require_permission("masterdata.write")),
                    db: Session = Depends(get_db)):
    user, company_id = context
    row = Supplier(company_id=company_id, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "Supplier", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/products", response_model=list[ProductOut])
def list_products(context=Depends(require_permission("masterdata.read")), db: Session = Depends(get_db)):
    _, company_id = context
    return list(db.scalars(select(Product).where(Product.company_id == company_id).order_by(Product.sku)).all())


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, context=Depends(require_permission("masterdata.write")),
                   db: Session = Depends(get_db)):
    user, company_id = context
    row = Product(company_id=company_id, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "Product", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(context=Depends(require_permission("masterdata.read")), db: Session = Depends(get_db)):
    _, company_id = context
    return list(db.scalars(select(Warehouse).where(Warehouse.company_id == company_id).order_by(Warehouse.name)).all())


@router.post("/warehouses", response_model=WarehouseOut, status_code=201)
def create_warehouse(payload: WarehouseCreate, context=Depends(require_permission("masterdata.write")),
                     db: Session = Depends(get_db)):
    user, company_id = context
    row = Warehouse(company_id=company_id, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "Warehouse", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/finance/accounts", response_model=list[AccountOut])
def list_accounts(context=Depends(require_permission("finance.read")), db: Session = Depends(get_db)):
    _, company_id = context
    return list(db.scalars(select(Account).where(Account.company_id == company_id).order_by(Account.code)).all())


@router.post("/finance/accounts", response_model=AccountOut, status_code=201)
def create_account(payload: AccountCreate, context=Depends(require_permission("finance.write")),
                   db: Session = Depends(get_db)):
    user, company_id = context
    row = Account(company_id=company_id, **payload.model_dump())
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "Account", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/finance/fx-rates", response_model=FxRateOut, status_code=201)
def create_fx_rate(payload: FxRateCreate, context=Depends(require_permission("finance.write")),
                   db: Session = Depends(get_db)):
    user, company_id = context
    code = payload.currency_code.upper()
    if not db.get(Currency, code):
        raise HTTPException(422, f"Unknown currency {code}")
    company = company_row(db, company_id)
    if code == company.functional_currency_code:
        raise HTTPException(422, "The functional currency always has an exchange rate of 1")
    row = FxRate(company_id=company_id, currency_code=code, rate_date=payload.rate_date,
                 functional_per_unit=payload.functional_per_unit, source=payload.source)
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "FxRate", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/finance/fx-rates", response_model=list[FxRateOut])
def list_fx_rates(context=Depends(require_permission("finance.read")), db: Session = Depends(get_db)):
    _, company_id = context
    return list(db.scalars(select(FxRate).where(FxRate.company_id == company_id)
                           .order_by(FxRate.rate_date.desc(), FxRate.currency_code)).all())


@router.post("/finance/journals", response_model=JournalOut, status_code=201)
def create_journal(payload: JournalCreate, context=Depends(require_permission("finance.write")),
                   db: Session = Depends(get_db)):
    user, company_id = context
    entry = JournalEntry(company_id=company_id, journal_number=payload.journal_number,
                         journal_date=payload.journal_date, description=payload.description,
                         status="DRAFT", created_by=user.id)
    db.add(entry)
    db.flush()
    for item in payload.lines:
        account = account_by_code(db, company_id, item.account_code)
        rate = fx_rate(db, company_id, item.currency_code, payload.journal_date, item.exchange_rate)
        add_journal_line(db, entry, account, item.currency_code.upper(), rate,
                         item.debit, item.credit, item.description or payload.description)
    audit(db, company_id, user.id, "CREATE", "JournalEntry", entry.id, "draft")
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/finance/journals", response_model=list[JournalOut])
def list_journals(context=Depends(require_permission("finance.read")), db: Session = Depends(get_db),
                  start: date | None = None, end: date | None = None):
    _, company_id = context
    stmt = select(JournalEntry).where(JournalEntry.company_id == company_id)
    if start:
        stmt = stmt.where(JournalEntry.journal_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.journal_date <= end)
    return list(db.scalars(stmt.order_by(JournalEntry.journal_date.desc(), JournalEntry.id.desc())).all())


@router.get("/finance/journals/{journal_id}/lines")
def journal_lines(journal_id: int, context=Depends(require_permission("finance.read")),
                  db: Session = Depends(get_db)):
    _, company_id = context
    entry = db.scalar(select(JournalEntry.id).where(JournalEntry.id == journal_id,
                                                     JournalEntry.company_id == company_id))
    if not entry:
        raise HTTPException(404, "Journal not found")
    lines = db.scalars(select(JournalLine).where(JournalLine.company_id == company_id,
                                                  JournalLine.journal_id == journal_id)
                       .order_by(JournalLine.id)).all()
    return [{"id": line.id, "account_id": line.account_id, "currency_code": line.currency_code,
             "exchange_rate": line.exchange_rate, "debit": line.debit, "credit": line.credit,
             "base_debit": line.base_debit, "base_credit": line.base_credit,
             "description": line.description} for line in lines]


@router.get("/finance/trial-balance")
def trial_balance(context=Depends(require_permission("finance.read")), db: Session = Depends(get_db),
                  start: date | None = None, end: date | None = None):
    _, company_id = context
    stmt = (select(Account.code, Account.name, Account.account_type,
                   func.sum(JournalLine.base_debit).label("debit"),
                   func.sum(JournalLine.base_credit).label("credit"))
            .join(JournalLine, (JournalLine.account_id == Account.id) &
                  (JournalLine.company_id == Account.company_id))
            .join(JournalEntry, (JournalEntry.id == JournalLine.journal_id) &
                  (JournalEntry.company_id == JournalLine.company_id))
            .where(Account.company_id == company_id, JournalEntry.status == "POSTED")
            .group_by(Account.code, Account.name, Account.account_type))
    if start:
        stmt = stmt.where(JournalEntry.journal_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.journal_date <= end)
    rows = db.execute(stmt.order_by(Account.code)).all()
    result = [{"account_code": code, "account_name": name, "account_type": kind,
               "debit_functional": money(Decimal(debit or 0)),
               "credit_functional": money(Decimal(credit or 0)),
               "net_debit_functional": money(Decimal(debit or 0) - Decimal(credit or 0))}
              for code, name, kind, debit, credit in rows]
    return {"company_id": company_id, "accounts": result,
            "total_debit_functional": money(sum((item["debit_functional"] for item in result), ZERO)),
            "total_credit_functional": money(sum((item["credit_functional"] for item in result), ZERO)),
            "period_start": start, "period_end": end}


@router.post("/finance/journals/{journal_id}/post", response_model=JournalOut)
def post_journal(journal_id: int, context=Depends(require_permission("finance.write")),
                 db: Session = Depends(get_db)):
    user, company_id = context
    lock_scoped_row(db, "journal_entries", company_id, journal_id)
    entry = db.scalar(select(JournalEntry).where(JournalEntry.id == journal_id,
                                                 JournalEntry.company_id == company_id))
    if not entry:
        raise HTTPException(404, "Journal not found")
    if entry.status != "DRAFT":
        raise HTTPException(409, "Only draft journals can be posted")
    totals = db.execute(
        select(func.count(JournalLine.id), func.sum(JournalLine.base_debit), func.sum(JournalLine.base_credit))
        .where(JournalLine.company_id == company_id, JournalLine.journal_id == entry.id)
    ).one()
    if totals[0] < 2 or money(Decimal(totals[1] or 0)) != money(Decimal(totals[2] or 0)):
        raise HTTPException(422, "Journal must contain at least two lines and balance in functional currency")
    entry.status = "POSTED"
    entry.posted_at = datetime.now(UTC)
    audit(db, company_id, user.id, "POST", "JournalEntry", entry.id)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/expenses", response_model=ExpenseOut, status_code=201)
def create_expense(payload: ExpenseCreate, context=Depends(require_permission("finance.write")),
                   db: Session = Depends(get_db)):
    user, company_id = context
    rate = fx_rate(db, company_id, payload.currency_code, payload.expense_date, payload.exchange_rate)
    row = Expense(company_id=company_id, expense_date=payload.expense_date, category=payload.category,
                  description=payload.description, currency_code=payload.currency_code.upper(), exchange_rate=rate,
                  amount=payload.amount, functional_amount=money(payload.amount * rate), status="RECORDED",
                  created_by=user.id, expense_account_code=payload.expense_account_code,
                  payment_account_code=payload.payment_account_code)
    db.add(row)
    db.flush()
    audit(db, company_id, user.id, "CREATE", "Expense", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/expenses/{expense_id}/post", response_model=ExpenseOut)
def post_expense(expense_id: int, context=Depends(require_permission("finance.write")),
                 db: Session = Depends(get_db)):
    user, company_id = context
    lock_scoped_row(db, "expenses", company_id, expense_id)
    row = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.company_id == company_id))
    if not row:
        raise HTTPException(404, "Expense not found")
    if row.status != "RECORDED":
        raise HTTPException(409, "Expense is already posted")
    debit = account_by_code(db, company_id, row.expense_account_code)
    credit = account_by_code(db, company_id, row.payment_account_code)
    create_system_journal(db, company_id, user.id, f"AUTO-E-{row.id}", row.expense_date,
                          f"Expense: {row.description}", [
        (debit, row.currency_code, row.exchange_rate, row.amount, ZERO, row.category),
        (credit, row.currency_code, row.exchange_rate, ZERO, row.amount, row.description),
    ], "EXPENSE", row.id)
    row.status = "POSTED"
    audit(db, company_id, user.id, "POST", "Expense", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(context=Depends(require_permission("finance.read")), db: Session = Depends(get_db),
                  start: date | None = None, end: date | None = None):
    _, company_id = context
    stmt = select(Expense).where(Expense.company_id == company_id)
    if start:
        stmt = stmt.where(Expense.expense_date >= start)
    if end:
        stmt = stmt.where(Expense.expense_date <= end)
    return list(db.scalars(stmt.order_by(Expense.expense_date.desc(), Expense.id.desc())).all())


@router.post("/sales/invoices", response_model=SalesInvoiceOut, status_code=201)
def create_sales_invoice(payload: SalesInvoiceCreate,
                         context=Depends(require_permission("sales.write")), db: Session = Depends(get_db)):
    user, company_id = context
    customer = db.scalar(select(Customer).where(Customer.id == payload.customer_id,
                                                 Customer.company_id == company_id,
                                                 Customer.is_active.is_(True)))
    if not customer:
        raise HTTPException(422, "Customer not found in this company")
    rate = fx_rate(db, company_id, payload.currency_code, payload.invoice_date, payload.exchange_rate)
    prepared = []
    subtotal = ZERO
    functional_subtotal = ZERO
    for line in payload.lines:
        product = db.scalar(select(Product).where(Product.id == line.product_id,
                                                   Product.company_id == company_id,
                                                   Product.is_active.is_(True)))
        warehouse = db.scalar(select(Warehouse).where(Warehouse.id == line.warehouse_id,
                                                       Warehouse.company_id == company_id))
        if not product or not warehouse:
            raise HTTPException(422, "Each invoice product and warehouse must belong to this company")
        subtotal += money(line.quantity * line.unit_price)
        functional_subtotal += money(money(line.quantity * line.unit_price) * rate)
        prepared.append((line, product))
    subtotal = money(subtotal)
    total = money(subtotal + payload.tax_amount)
    functional_subtotal = money(functional_subtotal)
    functional_tax = money(payload.tax_amount * rate)
    if total <= 0:
        raise HTTPException(422, "Invoice total must be greater than zero")
    invoice = SalesInvoice(company_id=company_id, customer_id=customer.id,
        invoice_number=payload.invoice_number, invoice_date=payload.invoice_date,
        currency_code=payload.currency_code.upper(), exchange_rate=rate,
        subtotal=subtotal, tax_amount=payload.tax_amount, total_amount=total,
        functional_subtotal=functional_subtotal, functional_tax=functional_tax,
        functional_total=functional_subtotal + functional_tax, status="DRAFT")
    db.add(invoice)
    db.flush()
    for line, product in prepared:
        db.add(SalesInvoiceLine(company_id=company_id, invoice_id=invoice.id, product_id=product.id,
            warehouse_id=line.warehouse_id, quantity=line.quantity, unit_price=line.unit_price,
            unit_cost_snapshot=product.unit_cost if product.track_inventory else ZERO))
    audit(db, company_id, user.id, "CREATE", "SalesInvoice", invoice.id, "draft")
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/sales/invoices", response_model=list[SalesInvoiceOut])
def list_sales_invoices(context=Depends(require_permission("sales.read")), db: Session = Depends(get_db),
                        start: date | None = None, end: date | None = None):
    _, company_id = context
    stmt = select(SalesInvoice).where(SalesInvoice.company_id == company_id)
    if start:
        stmt = stmt.where(SalesInvoice.invoice_date >= start)
    if end:
        stmt = stmt.where(SalesInvoice.invoice_date <= end)
    return list(db.scalars(stmt.order_by(SalesInvoice.invoice_date.desc(), SalesInvoice.id.desc())).all())


@router.post("/sales/invoices/{invoice_id}/post", response_model=SalesInvoiceOut)
def post_sales_invoice(invoice_id: int, context=Depends(require_permission("sales.write")),
                       db: Session = Depends(get_db)):
    user, company_id = context
    lock_scoped_row(db, "sales_invoices", company_id, invoice_id)
    invoice = db.scalar(select(SalesInvoice).where(SalesInvoice.id == invoice_id,
                                                    SalesInvoice.company_id == company_id))
    if not invoice:
        raise HTTPException(404, "Sales invoice not found")
    if invoice.status != "DRAFT":
        raise HTTPException(409, "Only draft invoices can be posted")
    lines = list(db.scalars(select(SalesInvoiceLine).where(SalesInvoiceLine.company_id == company_id,
                                                            SalesInvoiceLine.invoice_id == invoice.id)).all())
    for product_id in sorted({line.product_id for line in lines}):
        lock_product_stock(db, company_id, product_id)
    ar = account_by_code(db, company_id, "1100")
    sales = account_by_code(db, company_id, "4000")
    tax = account_by_code(db, company_id, "2100") if invoice.tax_amount else None
    functional_currency = company_row(db, company_id).functional_currency_code
    cogs_account = account_by_code(db, company_id, "5000")
    inventory_account = account_by_code(db, company_id, "1300")
    cogs = ZERO
    required_stock: dict[tuple[int, int], Decimal] = {}
    for line in lines:
        product = db.get(Product, line.product_id)
        if not product or product.company_id != company_id:
            raise HTTPException(422, "Invoice line product is invalid")
        if product.track_inventory:
            stock_key = (line.product_id, line.warehouse_id)
            required_stock[stock_key] = required_stock.get(stock_key, ZERO) + Decimal(line.quantity)
            company_units, company_value = stock_position(db, company_id, line.product_id)
            average_cost = money(company_value / company_units) if company_units > 0 else product.unit_cost
            line.unit_cost_snapshot = average_cost
            cogs += money(line.quantity * average_cost)
    for (product_id, warehouse_id), required in required_stock.items():
        available, _ = stock_position(db, company_id, product_id, warehouse_id)
        if available < required:
            product = db.get(Product, product_id)
            sku = product.sku if product else str(product_id)
            raise HTTPException(409, f"Insufficient stock for SKU {sku}: {available} available")
    entry = JournalEntry(company_id=company_id, journal_number=f"AUTO-S-{invoice.invoice_number}",
        journal_date=invoice.invoice_date, description=f"Sales invoice {invoice.invoice_number}",
        source_type="SALES_INVOICE", source_id=str(invoice.id), status="DRAFT", created_by=user.id)
    db.add(entry)
    db.flush()
    base_revenue = money(invoice.functional_subtotal)
    base_tax = money(invoice.functional_tax)
    total_base = money(base_revenue + base_tax)
    add_journal_line(db, entry, ar, invoice.currency_code, invoice.exchange_rate,
                     invoice.total_amount, ZERO, f"Receivable: {invoice.invoice_number}")
    # Use exact functional totals so source currency rounding never breaks the ledger.
    db.query(JournalLine).filter(JournalLine.company_id == company_id, JournalLine.journal_id == entry.id,
                                 JournalLine.account_id == ar.id).update({JournalLine.base_debit: total_base})
    if invoice.subtotal:
        add_journal_line(db, entry, sales, invoice.currency_code, invoice.exchange_rate,
                         ZERO, invoice.subtotal, f"Revenue: {invoice.invoice_number}")
        db.query(JournalLine).filter(JournalLine.company_id == company_id, JournalLine.journal_id == entry.id,
                                     JournalLine.account_id == sales.id).update({JournalLine.base_credit: base_revenue})
    if invoice.tax_amount and tax:
        add_journal_line(db, entry, tax, invoice.currency_code, invoice.exchange_rate,
                         ZERO, invoice.tax_amount, f"Tax payable: {invoice.invoice_number}")
        db.query(JournalLine).filter(JournalLine.company_id == company_id, JournalLine.journal_id == entry.id,
                                     JournalLine.account_id == tax.id).update({JournalLine.base_credit: base_tax})
    for line in lines:
        product = db.get(Product, line.product_id)
        if product and product.track_inventory and line.unit_cost_snapshot > 0:
            cost = money(line.quantity * line.unit_cost_snapshot)
            add_journal_line(db, entry, cogs_account, functional_currency, Decimal("1"), cost, ZERO,
                             f"COGS {product.sku}")
            add_journal_line(db, entry, inventory_account, functional_currency, Decimal("1"), ZERO, cost,
                             f"Inventory issue {product.sku}")
        if product and product.track_inventory:
            db.add(StockMovement(company_id=company_id, product_id=line.product_id,
                warehouse_id=line.warehouse_id, movement_date=invoice.invoice_date,
                movement_type="ISSUE", quantity=line.quantity, unit_cost=line.unit_cost_snapshot,
                reference=f"SALES:{invoice.invoice_number}", created_by=user.id))
    db.flush()
    totals = db.execute(select(func.sum(JournalLine.base_debit), func.sum(JournalLine.base_credit))
                        .where(JournalLine.company_id == company_id, JournalLine.journal_id == entry.id)).one()
    if money(Decimal(totals[0] or 0)) != money(Decimal(totals[1] or 0)):
        raise HTTPException(422, "Invoice journal is out of balance")
    entry.status = "POSTED"
    entry.posted_at = datetime.now(UTC)
    db.flush()
    invoice.status = "POSTED"
    audit(db, company_id, user.id, "POST", "SalesInvoice", invoice.id)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/purchases/bills", response_model=PurchaseBillOut, status_code=201)
def create_purchase_bill(payload: PurchaseBillCreate,
                         context=Depends(require_permission("purchases.write")), db: Session = Depends(get_db)):
    user, company_id = context
    supplier = db.scalar(select(Supplier).where(Supplier.id == payload.supplier_id,
                                                 Supplier.company_id == company_id,
                                                 Supplier.is_active.is_(True)))
    if not supplier:
        raise HTTPException(422, "Supplier not found in this company")
    rate = fx_rate(db, company_id, payload.currency_code, payload.bill_date, payload.exchange_rate)
    total = ZERO
    functional_total = ZERO
    prepared = []
    for line in payload.lines:
        product = db.scalar(select(Product).where(Product.id == line.product_id,
                                                   Product.company_id == company_id,
                                                   Product.is_active.is_(True)))
        warehouse = db.scalar(select(Warehouse).where(Warehouse.id == line.warehouse_id,
                                                       Warehouse.company_id == company_id))
        if not product or not warehouse:
            raise HTTPException(422, "Each bill product and warehouse must belong to this company")
        total += money(line.quantity * line.unit_cost)
        functional_total += money(money(line.quantity * line.unit_cost) * rate)
        prepared.append((line, product))
    total = money(total)
    functional_total = money(functional_total)
    if total <= 0:
        raise HTTPException(422, "Purchase bill total must be greater than zero")
    bill = PurchaseBill(company_id=company_id, supplier_id=supplier.id, bill_number=payload.bill_number,
        bill_date=payload.bill_date, currency_code=payload.currency_code.upper(), exchange_rate=rate,
        total_amount=total, functional_total=functional_total, status="DRAFT")
    db.add(bill)
    db.flush()
    for line, product in prepared:
        db.add(PurchaseBillLine(company_id=company_id, bill_id=bill.id, product_id=product.id,
            warehouse_id=line.warehouse_id, quantity=line.quantity, unit_cost=line.unit_cost))
    audit(db, company_id, user.id, "CREATE", "PurchaseBill", bill.id, "draft")
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/purchases/bills", response_model=list[PurchaseBillOut])
def list_purchase_bills(context=Depends(require_permission("purchases.read")), db: Session = Depends(get_db),
                        start: date | None = None, end: date | None = None):
    _, company_id = context
    stmt = select(PurchaseBill).where(PurchaseBill.company_id == company_id)
    if start:
        stmt = stmt.where(PurchaseBill.bill_date >= start)
    if end:
        stmt = stmt.where(PurchaseBill.bill_date <= end)
    return list(db.scalars(stmt.order_by(PurchaseBill.bill_date.desc(), PurchaseBill.id.desc())).all())


@router.post("/purchases/bills/{bill_id}/post", response_model=PurchaseBillOut)
def post_purchase_bill(bill_id: int, context=Depends(require_permission("purchases.write")),
                       db: Session = Depends(get_db)):
    user, company_id = context
    lock_scoped_row(db, "purchase_bills", company_id, bill_id)
    bill = db.scalar(select(PurchaseBill).where(PurchaseBill.id == bill_id, PurchaseBill.company_id == company_id))
    if not bill:
        raise HTTPException(404, "Purchase bill not found")
    if bill.status != "DRAFT":
        raise HTTPException(409, "Only draft bills can be posted")
    lines = list(db.scalars(select(PurchaseBillLine).where(PurchaseBillLine.company_id == company_id,
                                                            PurchaseBillLine.bill_id == bill.id)).all())
    for product_id in sorted({line.product_id for line in lines}):
        lock_product_stock(db, company_id, product_id)
    inventory = account_by_code(db, company_id, "1300")
    payable = account_by_code(db, company_id, "2000")
    # Aggregate the source-currency inventory debit so the payable and inventory control
    # accounts use the same rounded transaction total.
    journal_lines = [(inventory, bill.currency_code, bill.exchange_rate, bill.total_amount, ZERO,
                      f"Inventory receipt: {bill.bill_number}")]
    journal_lines.append((payable, bill.currency_code, bill.exchange_rate, ZERO, bill.total_amount,
                          f"Payable: {bill.bill_number}"))
    create_system_journal(db, company_id, user.id, f"AUTO-P-{bill.bill_number}", bill.bill_date,
                          f"Purchase bill {bill.bill_number}", journal_lines, "PURCHASE_BILL", bill.id)
    for line in lines:
        unit_cost_functional = money(line.unit_cost * bill.exchange_rate)
        _, current_value = stock_position(db, company_id, line.product_id)
        current_units, _ = stock_position(db, company_id, line.product_id)
        new_quantity = current_units + line.quantity
        if new_quantity > 0:
            product = db.get(Product, line.product_id)
            product.unit_cost = money((current_value + line.quantity * unit_cost_functional) / new_quantity)
        db.add(StockMovement(company_id=company_id, product_id=line.product_id,
            warehouse_id=line.warehouse_id, movement_date=bill.bill_date,
            movement_type="RECEIPT", quantity=line.quantity, unit_cost=unit_cost_functional,
            reference=f"PURCHASE:{bill.bill_number}", created_by=user.id))
    bill.status = "POSTED"
    audit(db, company_id, user.id, "POST", "PurchaseBill", bill.id)
    db.commit()
    db.refresh(bill)
    return bill


@router.post("/inventory/movements", response_model=StockMovementOut, status_code=201)
def create_stock_movement(payload: StockMovementCreate,
                          context=Depends(require_permission("inventory.write")), db: Session = Depends(get_db)):
    user, company_id = context
    kind = payload.movement_type.upper()
    if kind not in {"RECEIPT", "ISSUE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"}:
        raise HTTPException(422, "Unsupported movement type")
    product = db.scalar(select(Product).where(Product.id == payload.product_id, Product.company_id == company_id))
    warehouse = db.scalar(select(Warehouse).where(Warehouse.id == payload.warehouse_id,
                                                   Warehouse.company_id == company_id))
    if not product or not warehouse:
        raise HTTPException(422, "Product and warehouse must belong to this company")
    if not product.track_inventory:
        raise HTTPException(422, "Inventory movements are only valid for tracked products")
    lock_product_stock(db, company_id, product.id)
    available, current_value = stock_position(db, company_id, product.id, warehouse.id)
    if kind in {"ISSUE", "ADJUSTMENT_OUT"} and available < payload.quantity:
        raise HTTPException(409, f"Insufficient stock: {available} available")
    company_units, company_value = stock_position(db, company_id, product.id)
    average_cost = money(company_value / company_units) if company_units > 0 else product.unit_cost
    movement_unit_cost = payload.unit_cost
    if kind in {"ISSUE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT"} and movement_unit_cost == 0:
        movement_unit_cost = average_cost
    row = StockMovement(company_id=company_id, product_id=product.id, warehouse_id=warehouse.id,
        movement_date=payload.movement_date, movement_type=kind, quantity=payload.quantity,
        unit_cost=movement_unit_cost, reference=payload.reference, created_by=user.id)
    db.add(row)
    db.flush()
    if kind in {"RECEIPT", "ADJUSTMENT_IN"} and product.track_inventory:
        total_units, total_value = stock_position(db, company_id, product.id)
        if total_units > 0:
            product.unit_cost = money(total_value / total_units)
    movement_value = money(payload.quantity * movement_unit_cost)
    if movement_value > 0:
        inventory_account = account_by_code(db, company_id, "1300")
        if kind == "RECEIPT":
            counterpart = account_by_code(db, company_id, "3000")
            journal_lines = [
                (inventory_account, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), movement_value, ZERO, "Opening inventory receipt"),
                (counterpart, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), ZERO, movement_value, "Opening inventory balance"),
            ]
        elif kind == "ISSUE":
            counterpart = account_by_code(db, company_id, "5000")
            journal_lines = [
                (counterpart, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), movement_value, ZERO, "Manual inventory issue COGS"),
                (inventory_account, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), ZERO, movement_value, "Manual inventory issue"),
            ]
        elif kind == "ADJUSTMENT_IN":
            counterpart = account_by_code(db, company_id, "6000")
            journal_lines = [
                (inventory_account, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), movement_value, ZERO, "Inventory gain adjustment"),
                (counterpart, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), ZERO, movement_value, "Inventory adjustment offset"),
            ]
        else:
            counterpart = account_by_code(db, company_id, "6000")
            journal_lines = [
                (counterpart, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), movement_value, ZERO, "Inventory loss adjustment"),
                (inventory_account, company_row(db, company_id).functional_currency_code,
                 Decimal("1"), ZERO, movement_value, "Inventory adjustment offset"),
            ]
        create_system_journal(db, company_id, user.id, f"AUTO-STOCK-{row.id}",
            payload.movement_date, f"Stock {kind.lower()}: {payload.reference or row.id}",
            journal_lines, "STOCK_MOVEMENT", row.id)
    audit(db, company_id, user.id, "CREATE", "StockMovement", row.id)
    db.commit()
    db.refresh(row)
    return row


@router.get("/inventory/balances")
def inventory_balances(context=Depends(require_permission("inventory.read")), db: Session = Depends(get_db)):
    _, company_id = context
    rows = db.execute(
        select(StockMovement.product_id, StockMovement.warehouse_id,
               func.sum(stock_signed(StockMovement.movement_type)).label("quantity"),
               func.sum(stock_value_signed()).label("inventory_value"))
        .where(StockMovement.company_id == company_id)
        .group_by(StockMovement.product_id, StockMovement.warehouse_id)
    ).all()
    products = {p.id: p.sku for p in db.scalars(select(Product).where(Product.company_id == company_id)).all()}
    warehouses = {w.id: w.name for w in db.scalars(select(Warehouse).where(Warehouse.company_id == company_id)).all()}
    return [{"product_id": p, "sku": products.get(p), "warehouse_id": w,
             "warehouse": warehouses.get(w), "quantity": Decimal(q or 0),
             "inventory_value_functional": money(Decimal(value or 0))} for p, w, q, value in rows]


@router.get("/analytics/overview", response_model=OverviewOut)
def analytics_overview(context=Depends(require_permission("analytics.read")), db: Session = Depends(get_db),
                       start: date | None = Query(default=None), end: date | None = Query(default=None)):
    _, company_id = context
    today = date.today()
    start, end = start or today.replace(day=1), end or today
    if start > end:
        raise HTTPException(422, "start date must be on or before end date")
    company = company_row(db, company_id)
    revenue = db.scalar(select(func.coalesce(func.sum(JournalLine.base_credit - JournalLine.base_debit), 0))
        .join(JournalEntry, (JournalEntry.id == JournalLine.journal_id) &
              (JournalEntry.company_id == JournalLine.company_id))
        .join(Account, (Account.id == JournalLine.account_id) & (Account.company_id == JournalLine.company_id))
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "POSTED",
               JournalEntry.journal_date.between(start, end), Account.account_type == "REVENUE")) or ZERO
    expenses = db.scalar(select(func.coalesce(func.sum(JournalLine.base_debit - JournalLine.base_credit), 0))
        .join(JournalEntry, (JournalEntry.id == JournalLine.journal_id) &
              (JournalEntry.company_id == JournalLine.company_id))
        .join(Account, (Account.id == JournalLine.account_id) & (Account.company_id == JournalLine.company_id))
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "POSTED",
               JournalEntry.journal_date.between(start, end), Account.account_type == "EXPENSE",
               Account.code != "5000")) or ZERO
    cogs = db.scalar(select(func.coalesce(func.sum(JournalLine.base_debit), 0))
        .join(JournalEntry, (JournalEntry.id == JournalLine.journal_id) &
              (JournalEntry.company_id == JournalLine.company_id))
        .join(Account, (Account.id == JournalLine.account_id) & (Account.company_id == JournalLine.company_id))
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "POSTED",
               JournalEntry.journal_date.between(start, end), Account.code == "5000")) or ZERO
    invoice_count = db.scalar(select(func.count(SalesInvoice.id)).where(SalesInvoice.company_id == company_id,
        SalesInvoice.status == "POSTED", SalesInvoice.invoice_date.between(start, end))) or 0
    expense_count = db.scalar(select(func.count(Expense.id)).where(Expense.company_id == company_id,
        Expense.status == "POSTED", Expense.expense_date.between(start, end))) or 0
    units = db.scalar(select(func.coalesce(func.sum(stock_signed(StockMovement.movement_type)), 0))
        .where(StockMovement.company_id == company_id)) or ZERO
    revenue, expenses, cogs = Decimal(revenue), Decimal(expenses), Decimal(cogs)
    notes = ["Revenue excludes sales tax; sales are reported when invoices are posted.",
             "All money values are translated to the company functional currency using transaction-date FX snapshots.",
             "The profit estimate uses posted sales, posted COGS, and posted expenses for this period."]
    return OverviewOut(company_id=company_id, functional_currency_code=company.functional_currency_code,
        revenue=money(revenue), expenses=money(expenses), cost_of_goods_sold=money(cogs),
        net_profit_estimate=money(revenue - expenses - cogs), invoice_count=invoice_count,
        expense_count=expense_count, inventory_units=Decimal(units), period_start=start,
        period_end=end, notes=notes)


@router.get("/analytics/revenue-trend")
def revenue_trend(context=Depends(require_permission("analytics.read")), db: Session = Depends(get_db),
                   months: int = Query(default=6, ge=1, le=24)):
    _, company_id = context
    today = date.today()
    last_month_index = today.year * 12 + today.month - 1
    first_month_index = last_month_index - months + 1
    first_month = date(first_month_index // 12, first_month_index % 12 + 1, 1)
    activity = db.execute(select(JournalEntry.journal_date,
        func.sum(JournalLine.base_credit - JournalLine.base_debit))
        .join(JournalLine, (JournalLine.company_id == JournalEntry.company_id) &
              (JournalLine.journal_id == JournalEntry.id))
        .join(Account, (Account.company_id == JournalLine.company_id) &
              (Account.id == JournalLine.account_id))
        .where(JournalEntry.company_id == company_id, JournalEntry.status == "POSTED",
               JournalEntry.journal_date >= first_month, JournalEntry.journal_date <= today,
               Account.account_type == "REVENUE")
        .group_by(JournalEntry.journal_date)).all()
    totals: dict[tuple[int, int], Decimal] = {}
    for transaction_date, amount in activity:
        key = (transaction_date.year, transaction_date.month)
        totals[key] = totals.get(key, ZERO) + Decimal(amount or 0)
    series = []
    for offset in range(months):
        month_index = first_month_index + offset
        year, month = month_index // 12, month_index % 12 + 1
        series.append({"year": year, "month": month, "label": f"{year}-{month:02d}",
                       "revenue": money(totals.get((year, month), ZERO))})
    return {"company_id": company_id, "functional_currency_code": company_row(db, company_id).functional_currency_code,
            "months": series}


@router.get("/analytics/insights")
def offline_insights(context=Depends(require_permission("analytics.read")), db: Session = Depends(get_db),
                     start: date | None = Query(default=None), end: date | None = Query(default=None)):
    overview = analytics_overview(context, db, start, end)
    return {"engine": "local-rules-v1", "external_llm": False,
            "basis": {"start": overview.period_start, "end": overview.period_end,
                      "functional_currency_code": overview.functional_currency_code},
            "insights": insights_for_overview(overview),
            "limitations": ["Insights are deterministic rules over posted records, not a trained model.",
                            "No recommendation is generated when the underlying period lacks sufficient data."]}


@router.post("/analytics/warehouse/refresh")
def refresh_warehouse(context=Depends(require_permission("warehouse.refresh")), db: Session = Depends(get_db)):
    user, company_id = context
    posted = db.scalars(select(JournalEntry).where(JournalEntry.company_id == company_id,
                                                   JournalEntry.status == "POSTED")).all()
    existing = set(db.scalars(select(FactFinancialTransaction.source_journal_line_id)
                              .where(FactFinancialTransaction.company_id == company_id)).all())
    inserted = 0
    for entry in posted:
        if entry.id in existing:
            continue
        d = entry.journal_date
        date_key = d.year * 10000 + d.month * 100 + d.day
        if not db.get(DimDate, date_key):
            db.add(DimDate(date_key=date_key, date_value=d, year=d.year,
                           quarter=(d.month - 1) // 3 + 1, month=d.month, day=d.day))
            db.flush()
        lines = db.scalars(select(JournalLine).where(JournalLine.company_id == company_id,
                                                     JournalLine.journal_id == entry.id)).all()
        for line in lines:
            if line.id in existing:
                continue
            db.add(FactFinancialTransaction(company_id=company_id, date_key=date_key,
                account_id=line.account_id, currency_code=line.currency_code,
                debit_functional=line.base_debit, credit_functional=line.base_credit,
                source_journal_id=entry.id, source_journal_line_id=line.id))
            inserted += 1
    audit(db, company_id, user.id, "REFRESH", "DataWarehouse", company_id,
          f"Inserted {inserted} financial fact rows")
    db.commit()
    return {"company_id": company_id, "fact_rows_inserted": inserted, "status": "ok"}


@router.get("/audit/events")
def audit_events(context=Depends(require_permission("finance.read")), db: Session = Depends(get_db),
                 limit: int = Query(default=100, ge=1, le=500)):
    _, company_id = context
    rows = db.scalars(select(AuditEvent).where(AuditEvent.company_id == company_id)
                      .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit)).all()
    return [{"id": row.id, "user_id": row.user_id, "action": row.action,
             "entity_type": row.entity_type, "entity_id": row.entity_id,
             "details": row.details, "created_at": row.created_at} for row in rows]

