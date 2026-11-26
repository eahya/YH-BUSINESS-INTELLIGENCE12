"""Create the first company, administrator, starter permissions, and chart of accounts."""

from getpass import getpass

from sqlalchemy import select

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import Company, Currency, User
from app.services.provisioning import CURRENCIES, seed_reference_data, provision_company_defaults
from app.security import hash_password


def main() -> None:
    settings = get_settings()
    if settings.auto_create_schema and settings.app_env.lower() != "production":
        Base.metadata.create_all(bind=engine)
    name = input("Company name: ").strip()
    currency = input("Functional currency [USD]: ").strip().upper() or "USD"
    full_name = input("Administrator full name: ").strip()
    email = input("Administrator email: ").strip().lower()
    password = getpass("Administrator password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Choose a password with at least 12 characters.")
    if not name or not full_name or "@" not in email:
        raise SystemExit("Company name, administrator name, and valid email are required.")

    with SessionLocal.begin() as db:
        seed_reference_data(db)
        if not db.get(Currency, currency):
            raise SystemExit(f"Currency {currency} is not in the supported starter currency list.")
        if db.scalar(select(User).where(User.email == email)):
            raise SystemExit("That email already belongs to an account.")
        company = Company(name=name, functional_currency_code=currency)
        db.add(company)
        db.flush()
        user = User(email=email, full_name=full_name, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        provision_company_defaults(db, company, user)
        company_id = company.id
    print(f"Initialized company {name!r} (id {company_id}) and administrator {email!r}.")


if __name__ == "__main__":
    main()
