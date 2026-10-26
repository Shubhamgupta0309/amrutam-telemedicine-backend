from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.analytics import service
from app.modules.analytics.schemas import AnalyticsSummary
from app.modules.auth.dependencies import require_roles
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["Admin & Analytics"])


@router.get("/analytics", response_model=AnalyticsSummary)
def get_analytics(
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Retrieve system-wide operational metrics, consultation counts, and revenues. Admin only."""
    return service.get_admin_analytics(db=db)
