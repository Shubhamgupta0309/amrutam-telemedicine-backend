import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Dict, List
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import correlation_id_ctx, logger, setup_logging
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.doctors.router import router as doctors_router
from app.modules.bookings.router import router as bookings_router
from app.modules.clinical.router import router as clinical_router
from app.modules.payments.router import router as payments_router
from app.modules.analytics.router import router as analytics_router
from app.observability.health import router as health_router
from app.observability.metrics import router as metrics_router, HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

# Configure JSON structured logging
setup_logging(level="DEBUG" if settings.DEBUG else "INFO")

# In-memory sliding window rate limiter
RATE_LIMIT_BUCKET: Dict[str, List[float]] = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist
    Base.metadata.create_all(bind=engine)
    logger.info("Application startup: database tables verified.")

    # Seed initial Admin user if not exists
    db = SessionLocal()
    try:
        from app.modules.users.models import User, Profile
        from app.core.security import get_password_hash
        admin_email = "admin@amrutam.co.in"
        existing_admin = db.scalar(select(User).where(User.email == admin_email))
        if not existing_admin:
            admin_user = User(
                email=admin_email,
                password_hash=get_password_hash("Admin@Amrutam2026!"),
                role="admin",
                status="active",
                mfa_enabled=False,
            )
            db.add(admin_user)
            db.flush()
            admin_profile = Profile(
                user_id=admin_user.id,
                name="Amrutam System Administrator",
                timezone="Asia/Kolkata",
            )
            db.add(admin_profile)
            db.commit()
            logger.info("Default administrator seeded: admin@amrutam.co.in")
    except Exception as exc:
        logger.error(f"Error checking/seeding admin: {exc}")
    finally:
        db.close()

    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade Telemedicine Backend API for Amrutam.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_and_metrics_middleware(request: Request, call_next):
    # Extract or generate Correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = correlation_id_ctx.set(correlation_id)

    # Simple Token-Bucket / Sliding Window Rate Limiter
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    RATE_LIMIT_BUCKET[client_ip] = [t for t in RATE_LIMIT_BUCKET[client_ip] if now - t < 60]

    # Don't rate limit health and metrics
    if not (request.url.path.startswith("/health") or request.url.path.startswith("/metrics")):
        if len(RATE_LIMIT_BUCKET[client_ip]) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "detail": "Rate limit exceeded. Maximum 60 requests per minute.",
                    "correlation_id": correlation_id,
                },
                headers={"X-Correlation-ID": correlation_id, "Retry-After": "60"},
            )
        RATE_LIMIT_BUCKET[client_ip].append(now)

    # Latency tracking
    start_time = time.time()
    try:
        response: Response = await call_next(request)
        duration = time.time() - start_time

        # Track Prometheus metrics
        endpoint = request.url.path
        HTTP_REQUESTS_TOTAL.labels(method=request.method, endpoint=endpoint, status_code=response.status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, endpoint=endpoint).observe(duration)

        response.headers["X-Correlation-ID"] = correlation_id
        return response
    except Exception as exc:
        duration = time.time() - start_time
        logger.error(f"Unhandled exception during request processing: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "detail": "An unexpected error occurred while processing your request.",
                "correlation_id": correlation_id,
            },
            headers={"X-Correlation-ID": correlation_id},
        )
    finally:
        correlation_id_ctx.reset(token)


from fastapi.encoders import jsonable_encoder

# Exception Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    correlation_id = correlation_id_ctx.get()
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.detail,
            "correlation_id": correlation_id,
            **exc.extra
        },
        headers={"X-Correlation-ID": correlation_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    correlation_id = correlation_id_ctx.get()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "VALIDATION_ERROR",
            "detail": "Validation error in request parameters or body.",
            "errors": jsonable_encoder(exc.errors()),
            "correlation_id": correlation_id,
        },
        headers={"X-Correlation-ID": correlation_id},
    )


# Register Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(doctors_router, prefix=settings.API_V1_STR)
app.include_router(bookings_router, prefix=settings.API_V1_STR)
app.include_router(clinical_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(health_router)
app.include_router(metrics_router)


@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/health/live",
        "metrics": "/metrics"
    }
