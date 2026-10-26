from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Observability & Health"])


@router.get("/live", status_code=status.HTTP_200_OK)
def liveness_check():
    """Kubernetes / Docker liveness probe: returns 200 if process is running."""
    return {"status": "alive"}


@router.get("/ready")
def readiness_check(response: Response, db: Session = Depends(get_db)):
    """
    Kubernetes / Docker readiness probe: verifies database connection is active.
    Returns 503 Service Unavailable if dependent services fail.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected"
        }
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": "disconnected",
            "error": str(e)
        }
