from typing import List, Callable
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token, oauth2_scheme
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.doctors.models import Doctor


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedException(detail="Invalid token type")

    user_id: str = payload.get("sub")
    if not user_id:
        raise UnauthorizedException(detail="Could not validate credentials")

    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise UnauthorizedException(detail="User no longer exists")

    if user.status != "active":
        raise ForbiddenException(detail="Account is suspended or deactivated")

    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                detail=f"Role '{current_user.role}' is not authorized to access this resource"
            )
        return current_user
    return role_checker


def get_current_verified_doctor(
    current_user: User = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> Doctor:
    doctor = db.scalar(select(Doctor).where(Doctor.user_id == current_user.id))
    if not doctor:
        raise ForbiddenException(detail="Doctor profile not found")

    if doctor.verification_status != "VERIFIED":
        raise ForbiddenException(
            detail=f"Doctor account is currently {doctor.verification_status}. Must be VERIFIED by admin."
        )

    return doctor
