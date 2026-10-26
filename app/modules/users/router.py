from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.users.models import User, Profile
from app.modules.users.schemas import ProfileUpdate, UserMeResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserMeResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve current authenticated user's profile and details."""
    return current_user


@router.put("/me", response_model=UserMeResponse)
def update_me(
    update_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current authenticated user's profile information."""
    if not current_user.profile:
        profile = Profile(
            user_id=current_user.id,
            name="User",
            timezone="UTC"
        )
        db.add(profile)
        current_user.profile = profile

    if update_data.name is not None:
        current_user.profile.name = update_data.name.strip()
    if update_data.phone is not None:
        current_user.profile.phone = update_data.phone.strip()
    if update_data.timezone is not None:
        current_user.profile.timezone = update_data.timezone.strip()

    db.commit()
    db.refresh(current_user)
    return current_user
