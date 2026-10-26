from datetime import timedelta
from typing import Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_mfa_secret,
    get_mfa_uri,
    get_password_hash,
    verify_mfa_code,
    verify_password,
)
from app.modules.auth.schemas import (
    MFAChallengeResponse,
    MFASetupResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.modules.audit.service import record_audit_log
from app.modules.users.models import Profile, User
from app.modules.doctors.models import Doctor


def register_user(db: Session, data: UserRegister, ip_address: Optional[str] = None) -> User:
    normalized_email = data.email.lower().strip()

    # Check for existing email
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user:
        raise ConflictException(detail="A user with this email already exists")

    # Validate doctor specific fields
    if data.role == "doctor":
        if not data.specialty or not data.registration_number:
            raise ValidationException(detail="Doctor registration requires specialty and registration_number")
        existing_doc = db.scalar(
            select(Doctor).where(Doctor.registration_number == data.registration_number.strip())
        )
        if existing_doc:
            raise ConflictException(detail="A doctor with this registration number already exists")

    # Hash password securely
    hashed_pwd = get_password_hash(data.password)

    # Create User
    new_user = User(
        email=normalized_email,
        password_hash=hashed_pwd,
        role=data.role,
        status="active",
        mfa_enabled=False,
    )
    db.add(new_user)
    db.flush()

    # Create Profile
    new_profile = Profile(
        user_id=new_user.id,
        name=data.name.strip(),
        phone=data.phone.strip() if data.phone else None,
        timezone=data.timezone,
    )
    db.add(new_profile)

    # Create Doctor record if applicable
    if data.role == "doctor":
        new_doctor = Doctor(
            user_id=new_user.id,
            specialty=data.specialty.strip(),
            registration_number=data.registration_number.strip(),
            verification_status="PENDING",
            consultation_fee=data.consultation_fee or 500.0,
        )
        db.add(new_doctor)

    record_audit_log(
        db=db,
        action="USER_REGISTER",
        resource_type="user",
        actor_id=new_user.id,
        resource_id=new_user.id,
        ip_address=ip_address,
        details={"role": data.role, "email": normalized_email},
    )

    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(
    db: Session,
    credentials: UserLogin,
    ip_address: Optional[str] = None
) -> Union[TokenResponse, MFAChallengeResponse]:
    normalized_email = credentials.email.lower().strip()
    user = db.scalar(select(User).where(User.email == normalized_email))

    if not user or not verify_password(credentials.password, user.password_hash):
        record_audit_log(
            db=db,
            action="LOGIN_FAILED",
            resource_type="auth",
            actor_id=None,
            ip_address=ip_address,
            details={"email": normalized_email, "reason": "invalid_credentials"},
        )
        db.commit()
        raise UnauthorizedException(detail="Incorrect email or password")

    if user.status != "active":
        raise ForbiddenException(detail="User account is inactive or suspended")

    # Check if MFA is required
    if user.mfa_enabled:
        temp_token = create_access_token(
            subject=user.id,
            role=user.role,
            expires_delta=timedelta(minutes=5),
            extra_claims={"type": "mfa_challenge"},
        )
        record_audit_log(
            db=db,
            action="LOGIN_MFA_CHALLENGE",
            resource_type="auth",
            actor_id=user.id,
            ip_address=ip_address,
        )
        db.commit()
        return MFAChallengeResponse(temp_token=temp_token)

    # Generate full access tokens
    access_token = create_access_token(subject=user.id, role=user.role)
    refresh_token = create_refresh_token(subject=user.id)

    record_audit_log(
        db=db,
        action="LOGIN_SUCCESS",
        resource_type="auth",
        actor_id=user.id,
        ip_address=ip_address,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role,
        user_id=user.id,
    )


def setup_mfa(db: Session, user: User) -> MFASetupResponse:
    secret = generate_mfa_secret()
    user.mfa_secret = secret
    db.commit()

    otpauth_url = get_mfa_uri(secret, user.email)
    return MFASetupResponse(secret=secret, otpauth_url=otpauth_url)


def verify_mfa_login(
    db: Session,
    code: str,
    temp_token: Optional[str] = None,
    current_user: Optional[User] = None,
    ip_address: Optional[str] = None,
) -> TokenResponse:
    user = current_user
    if not user and temp_token:
        payload = decode_token(temp_token)
        if payload.get("type") != "mfa_challenge":
            raise UnauthorizedException(detail="Invalid MFA challenge token")
        user_id = payload.get("sub")
        user = db.scalar(select(User).where(User.id == user_id))

    if not user:
        raise UnauthorizedException(detail="User not found")

    if not user.mfa_secret:
        raise ValidationException(detail="MFA is not configured for this account")

    if not verify_mfa_code(user.mfa_secret, code):
        record_audit_log(
            db=db,
            action="MFA_VERIFY_FAILED",
            resource_type="auth",
            actor_id=user.id,
            ip_address=ip_address,
        )
        db.commit()
        raise UnauthorizedException(detail="Invalid MFA verification code")

    # Mark MFA as enabled if this was during setup
    if not user.mfa_enabled:
        user.mfa_enabled = True

    access_token = create_access_token(subject=user.id, role=user.role)
    refresh_token = create_refresh_token(subject=user.id)

    record_audit_log(
        db=db,
        action="MFA_VERIFY_SUCCESS",
        resource_type="auth",
        actor_id=user.id,
        ip_address=ip_address,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role,
        user_id=user.id,
    )


def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise UnauthorizedException(detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = db.scalar(select(User).where(User.id == user_id))
    if not user or user.status != "active":
        raise UnauthorizedException(detail="User is inactive or not found")

    new_access_token = create_access_token(subject=user.id, role=user.role)
    new_refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        role=user.role,
        user_id=user.id,
    )
