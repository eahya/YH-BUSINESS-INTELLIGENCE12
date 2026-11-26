from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer,
    Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

MONEY = Numeric(19, 4, asdecimal=True)
RATE = Numeric(19, 8, asdecimal=True)


class Currency(Base):
    __tablename__ = "currencies"
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    minor_units: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    functional_currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyMembership(Base):
    __tablename__ = "company_memberships"
    __table_args__ = (UniqueConstraint("company_id", "user_id"), UniqueConstraint("company_id", "id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("company_id", "code"), UniqueConstraint("company_id", "id"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class MembershipRole(Base):
    __tablename__ = "membership_roles"
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "membership_id"], ["company_memberships.company_id", "company_memberships.id"]),
        ForeignKeyConstraint(["company_id", "role_id"], ["roles.company_id", "roles.id"]),
    )
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    membership_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)


class Permission(Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    description: Mapped[str] = mapped_column(String(160), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (ForeignKeyConstraint(["company_id", "role_id"], ["roles.company_id", "roles.id"]),)
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permissions.code"), primary_key=True)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "code"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "code"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "sku"),
                      CheckConstraint("unit_cost >= 0 AND selling_price >= 0", name="ck_product_prices"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    selling_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    track_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "code"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)


class FxRate(Base):
    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("company_id", "currency_code", "rate_date"),
                      CheckConstraint("functional_per_unit > 0", name="ck_fx_rate_positive"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    functional_per_unit: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="MANUAL")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "code"),
                      CheckConstraint("account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')",
                                      name="ck_account_type"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "journal_number"),
                      CheckConstraint("status IN ('DRAFT','POSTED','VOID')", name="ck_journal_status"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    journal_number: Mapped[str] = mapped_column(String(50), nullable=False)
    journal_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="DRAFT")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        UniqueConstraint("company_id", "id"),
        ForeignKeyConstraint(["company_id", "journal_id"], ["journal_entries.company_id", "journal_entries.id"]),
        ForeignKeyConstraint(["company_id", "account_id"], ["accounts.company_id", "accounts.id"]),
        CheckConstraint("debit >= 0 AND credit >= 0 AND NOT (debit > 0 AND credit > 0)", name="ck_journal_line_side"),
        CheckConstraint("base_debit >= 0 AND base_credit >= 0 AND NOT (base_debit > 0 AND base_credit > 0)",
                        name="ck_journal_line_base_side"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    journal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    debit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    credit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    base_debit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    base_credit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String(250))


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_expense_positive"),
                      CheckConstraint("status IN ('RECORDED','POSTED')", name="ck_expense_status"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    functional_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="RECORDED")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    expense_account_code: Mapped[str] = mapped_column(String(30), nullable=False, default="6000")
    payment_account_code: Mapped[str] = mapped_column(String(30), nullable=False, default="1000")


class SalesInvoice(Base):
    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint("company_id", "id"), UniqueConstraint("company_id", "invoice_number"),
        ForeignKeyConstraint(["company_id", "customer_id"], ["customers.company_id", "customers.id"]),
        CheckConstraint("subtotal >= 0 AND tax_amount >= 0 AND total_amount >= 0", name="ck_sales_amounts"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    functional_subtotal: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    functional_tax: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    functional_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="DRAFT")


class SalesInvoiceLine(Base):
    __tablename__ = "sales_invoice_lines"
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "invoice_id"], ["sales_invoices.company_id", "sales_invoices.id"]),
        ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id"]),
        ForeignKeyConstraint(["company_id", "warehouse_id"], ["warehouses.company_id", "warehouses.id"]),
        CheckConstraint("quantity > 0 AND unit_price >= 0 AND unit_cost_snapshot >= 0",
                        name="ck_sales_line_values"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class PurchaseBill(Base):
    __tablename__ = "purchase_bills"
    __table_args__ = (UniqueConstraint("company_id", "bill_number"),
                      ForeignKeyConstraint(["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id"]))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    bill_number: Mapped[str] = mapped_column(String(50), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    functional_total: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="DRAFT")


class PurchaseBillLine(Base):
    __tablename__ = "purchase_bill_lines"
    __table_args__ = (
        ForeignKeyConstraint(["company_id", "bill_id"], ["purchase_bills.company_id", "purchase_bills.id"]),
        ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id"]),
        ForeignKeyConstraint(["company_id", "warehouse_id"], ["warehouses.company_id", "warehouses.id"]),
        CheckConstraint("quantity > 0 AND unit_cost >= 0", name="ck_purchase_line_values"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bill_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_company_product_warehouse", "company_id", "product_id", "warehouse_id"),
        ForeignKeyConstraint(["company_id", "product_id"], ["products.company_id", "products.id"]),
        ForeignKeyConstraint(["company_id", "warehouse_id"], ["warehouses.company_id", "warehouses.id"]),
        CheckConstraint("quantity > 0 AND unit_cost >= 0", name="ck_stock_positive"),
        CheckConstraint("movement_type IN ('RECEIPT','ISSUE','ADJUSTMENT_IN','ADJUSTMENT_OUT')",
                        name="ck_stock_movement_type"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    reference: Mapped[str | None] = mapped_column(String(100))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DimDate(Base):
    __tablename__ = "dim_date"
    date_key: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_value: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)


class FactFinancialTransaction(Base):
    """Warehouse fact at posted journal-line grain; base amounts are functional currency."""
    __tablename__ = "fact_financial_transactions"
    __table_args__ = (
        UniqueConstraint("company_id", "source_journal_line_id"),
        ForeignKeyConstraint(["company_id", "account_id"], ["accounts.company_id", "accounts.id"]),
        ForeignKeyConstraint(["company_id", "source_journal_id"], ["journal_entries.company_id", "journal_entries.id"]),
        ForeignKeyConstraint(["company_id", "source_journal_line_id"], ["journal_lines.company_id", "journal_lines.id"]),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date_key: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(ForeignKey("currencies.code"), nullable=False)
    debit_functional: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    credit_functional: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    source_journal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_journal_line_id: Mapped[int] = mapped_column(Integer, nullable=False)



