from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import (
    Account, Company, CompanyMembership, Currency, Customer, MembershipRole, Permission,
    Role, RolePermission, User,
)
from app.security import hash_password

PERMISSIONS = [
    "masterdata.read", "masterdata.write", "finance.read", "finance.write", "sales.read",
    "sales.write", "purchases.read", "purchases.write", "inventory.read", "inventory.write",
    "analytics.read", "warehouse.refresh", "security.manage",
]


@pytest.fixture
def client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        for code, name in [("USD", "US Dollar"), ("EUR", "Euro")]:
            db.add(Currency(code=code, name=name, minor_units=2))
        company = Company(name="Northwind Demo", functional_currency_code="USD")
        other = Company(name="Other Tenant", functional_currency_code="USD")
        db.add_all([company, other])
        db.flush()
        user = User(email="admin@example.test", full_name="Demo Admin", password_hash=hash_password("correct-horse-battery"))
        db.add(user)
        db.flush()
        membership = CompanyMembership(company_id=company.id, user_id=user.id, is_active=True)
        db.add(membership)
        db.flush()
        role = Role(company_id=company.id, code="ADMIN", name="Administrator")
        db.add(role)
        db.flush()
        db.add(MembershipRole(company_id=company.id, membership_id=membership.id, role_id=role.id))
        for code in PERMISSIONS:
            db.add(Permission(code=code, description=code))
            db.add(RolePermission(company_id=company.id, role_id=role.id, permission_code=code))
        for code, name, kind in [
            ("1000", "Cash", "ASSET"), ("1100", "Receivable", "ASSET"),
            ("1300", "Inventory", "ASSET"), ("2000", "Payable", "LIABILITY"),
            ("2100", "Tax payable", "LIABILITY"), ("3000", "Retained earnings", "EQUITY"),
            ("4000", "Sales", "REVENUE"),
            ("5000", "Cost of goods sold", "EXPENSE"), ("6000", "Operating expenses", "EXPENSE"),
        ]:
            db.add(Account(company_id=company.id, code=code, name=name, account_type=kind))
        db.flush()
        other_customer = Customer(company_id=other.id, code="PRIVATE", name="Private Customer")
        db.add(other_customer)

    def override_get_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client, factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def auth(client):
    test_client, _ = client
    response = test_client.post("/api/v1/auth/token", json={
        "email": "admin@example.test", "password": "correct-horse-battery",
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    companies = test_client.get("/api/v1/companies", headers={"Authorization": f"Bearer {token}"})
    company_id = companies.json()[0]["id"]
    return test_client, {"Authorization": f"Bearer {token}", "X-Company-ID": str(company_id)}, company_id
