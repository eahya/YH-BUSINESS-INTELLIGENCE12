from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str


class UserInviteCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    temporary_password: str | None = Field(default=None, min_length=12, max_length=128)
    role_code: str = Field(min_length=1, max_length=40)


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    permission_codes: list[str] = Field(min_length=1, max_length=40)


class RoleOut(BaseModel):
    code: str
    name: str
    permission_codes: list[str]


class CompanyOut(ORMModel):
    id: int
    name: str
    functional_currency_code: str
    country_code: str | None


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    functional_currency_code: str = Field(min_length=3, max_length=3)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("functional_currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)


class CustomerOut(ORMModel):
    id: int
    code: str
    name: str
    email: EmailStr | None
    phone: str | None
    is_active: bool


class SupplierCreate(CustomerCreate):
    pass


class SupplierOut(CustomerOut):
    pass


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    selling_price: Decimal = Field(default=Decimal("0"), ge=0)
    track_inventory: bool = True


class ProductOut(ORMModel):
    id: int
    sku: str
    name: str
    category: str | None
    unit_cost: Decimal
    selling_price: Decimal
    track_inventory: bool
    is_active: bool


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=150)


class WarehouseOut(ORMModel):
    id: int
    code: str
    name: str


class FxRateCreate(BaseModel):
    currency_code: str = Field(min_length=3, max_length=3)
    rate_date: date
    functional_per_unit: Decimal = Field(gt=0)
    source: str = Field(default="MANUAL", max_length=80)


class FxRateOut(ORMModel):
    id: int
    currency_code: str
    rate_date: date
    functional_per_unit: Decimal
    source: str


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=150)
    account_type: str

    @field_validator("account_type")
    @classmethod
    def valid_type(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"}:
            raise ValueError("Invalid account type")
        return normalized


class AccountOut(ORMModel):
    id: int
    code: str
    name: str
    account_type: str
    is_active: bool


class JournalLineInput(BaseModel):
    account_code: str = Field(min_length=1, max_length=30)
    currency_code: str = Field(min_length=3, max_length=3)
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=250)

    @model_validator(mode="after")
    def one_side(self):
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Each line must have a positive debit or credit, never both")
        return self


class JournalCreate(BaseModel):
    journal_number: str = Field(min_length=1, max_length=50)
    journal_date: date
    description: str = Field(min_length=1, max_length=300)
    lines: list[JournalLineInput] = Field(min_length=2, max_length=200)


class JournalLineOut(ORMModel):
    id: int
    account_id: int
    currency_code: str
    exchange_rate: Decimal
    debit: Decimal
    credit: Decimal
    base_debit: Decimal
    base_credit: Decimal
    description: str | None


class JournalOut(ORMModel):
    id: int
    journal_number: str
    journal_date: date
    description: str
    status: str


class ExpenseCreate(BaseModel):
    expense_date: date
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    currency_code: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(gt=0)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    expense_account_code: str = Field(default="6000", max_length=30)
    payment_account_code: str = Field(default="1000", max_length=30)


class ExpenseOut(ORMModel):
    id: int
    expense_date: date
    category: str
    description: str
    currency_code: str
    exchange_rate: Decimal
    amount: Decimal
    functional_amount: Decimal
    status: str


class InvoiceLineInput(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class SalesInvoiceCreate(BaseModel):
    customer_id: int
    invoice_number: str = Field(min_length=1, max_length=50)
    invoice_date: date
    currency_code: str = Field(min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    lines: list[InvoiceLineInput] = Field(min_length=1, max_length=200)


class SalesInvoiceOut(ORMModel):
    id: int
    customer_id: int
    invoice_number: str
    invoice_date: date
    currency_code: str
    exchange_rate: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    functional_total: Decimal
    status: str


class PurchaseLineInput(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class PurchaseBillCreate(BaseModel):
    supplier_id: int
    bill_number: str = Field(min_length=1, max_length=50)
    bill_date: date
    currency_code: str = Field(min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    lines: list[PurchaseLineInput] = Field(min_length=1, max_length=200)


class PurchaseBillOut(ORMModel):
    id: int
    supplier_id: int
    bill_number: str
    bill_date: date
    currency_code: str
    exchange_rate: Decimal
    total_amount: Decimal
    functional_total: Decimal
    status: str


class StockMovementCreate(BaseModel):
    product_id: int
    warehouse_id: int
    movement_date: date
    movement_type: str
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    reference: str | None = Field(default=None, max_length=100)


class StockMovementOut(ORMModel):
    id: int
    product_id: int
    warehouse_id: int
    movement_date: date
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal
    reference: str | None


class OverviewOut(BaseModel):
    company_id: int
    functional_currency_code: str
    revenue: Decimal
    expenses: Decimal
    cost_of_goods_sold: Decimal
    net_profit_estimate: Decimal
    invoice_count: int
    expense_count: int
    inventory_units: Decimal
    period_start: date
    period_end: date
    notes: list[str]
