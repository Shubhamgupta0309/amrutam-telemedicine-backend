from typing import Union
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    MFAChallengeResponse,
    MFASetupResponse,
    MFAVerifyRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    data: UserRegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new patient or doctor."""
    client_ip = request.client.host if request.client else None
    user = service.register_user(db=db, data=data, ip_address=client_ip)
    return {
        "message": "User registered successfully",
        "user_id": user.id,
        "email": user.email,
        "role": user.role
    }


@router.post("/login", response_model=Union[TokenResponse, MFAChallengeResponse])
def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate with email and password."""
    client_ip = request.client.host if request.client else None
    return service.authenticate_user(db=db, credentials=credentials, ip_address=client_ip)


@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate MFA secret and QR code URI for authenticator app."""
    return service.setup_mfa(db=db, user=current_user)


@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa(
    data: MFAVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Verify MFA code to finalize setup or complete privileged login."""
    client_ip = request.client.host if request.client else None
    return service.verify_mfa_login(
        db=db,
        code=data.code,
        temp_token=data.temp_token,
        ip_address=client_ip
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    data: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """Exchange a valid refresh token for a new access token."""
    return service.refresh_access_token(db=db, refresh_token=data.refresh_token)
