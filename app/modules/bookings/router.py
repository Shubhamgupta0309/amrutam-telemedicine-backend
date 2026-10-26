from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_roles
from app.modules.bookings import service
from app.modules.bookings.schemas import BookingCancelRequest, BookingCreate, BookingRead
from app.modules.users.models import User

router = APIRouter(prefix="/bookings", tags=["Bookings & Appointments"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_data: BookingCreate,
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """
    Book an appointment slot atomically.
    Requires an Idempotency-Key header to prevent duplicate charges and reservations.
    """
    client_ip = request.client.host if request.client else None
    result, status_code = service.book_appointment_atomic(
        db=db,
        patient_id=current_user.id,
        booking_data=booking_data,
        idempotency_key=idempotency_key,
        ip_address=client_ip,
    )
    response.status_code = status_code
    return result


@router.get("", response_model=List[BookingRead])
def list_bookings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List bookings for current authenticated user (patient, doctor, or admin)."""
    items, _ = service.get_user_bookings(db=db, user=current_user, page=page, size=size)
    return items


@router.get("/{id}", response_model=BookingRead)
def get_booking(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details of a specific booking with access verification."""
    return service.get_booking_details(db=db, booking_id=id, user=current_user)


@router.post("/{id}/cancel", response_model=BookingRead)
def cancel_booking(
    id: str,
    cancel_data: BookingCancelRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a scheduled consultation and release the slot back to AVAILABLE."""
    client_ip = request.client.host if request.client else None
    return service.cancel_booking(
        db=db,
        booking_id=id,
        user=current_user,
        reason=cancel_data.reason,
        ip_address=client_ip,
    )
