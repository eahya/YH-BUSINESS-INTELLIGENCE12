from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import CompanyMembership, MembershipRole, Permission, Role, RolePermission, User

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iss": settings.jwt_issuer, "iat": now,
         "exp": now + timedelta(minutes=settings.access_token_minutes)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def get_current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=["HS256"],
            issuer=get_settings().jwt_issuer,
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or missing")
    return user


def get_company_context(
    company_id: int = Header(alias="X-Company-ID"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, int]:
    membership = db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.id,
            CompanyMembership.is_active.is_(True),
        )
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No active membership for this company")
    if db.get_bind().dialect.name == "mssql":
        db.execute(text("EXEC sys.sp_set_session_context @key=N'company_id', @value=:company_id"),
                   {"company_id": company_id})
    return user, company_id


def require_permission(permission_code: str):
    def dependency(
        context: tuple[User, int] = Depends(get_company_context),
        db: Session = Depends(get_db),
    ) -> tuple[User, int]:
        user, company_id = context
        allowed = db.scalar(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_code == Permission.code)
            .join(Role, (Role.id == RolePermission.role_id) & (Role.company_id == RolePermission.company_id))
            .join(MembershipRole, (MembershipRole.role_id == Role.id) &
                  (MembershipRole.company_id == Role.company_id))
            .join(CompanyMembership, (CompanyMembership.id == MembershipRole.membership_id) &
                  (CompanyMembership.company_id == MembershipRole.company_id))
            .where(
                CompanyMembership.user_id == user.id,
                CompanyMembership.company_id == company_id,
                CompanyMembership.is_active.is_(True),
                Role.company_id == company_id,
                Permission.code == permission_code,
            )
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=f"Permission required: {permission_code}")
        return context

    return dependency
