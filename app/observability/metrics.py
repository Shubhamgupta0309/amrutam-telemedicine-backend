import time
from fastapi import APIRouter, Request, Response
from prometheus_client import CollectorRegistry, CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

router = APIRouter(tags=["Observability & Metrics"])

# Clean Prometheus registry focused exclusively on application metrics
metrics_registry = CollectorRegistry()

# Prometheus Metrics Definitions
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
    registry=metrics_registry,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    registry=metrics_registry,
)

BOOKING_OPERATIONS_TOTAL = Counter(
    "booking_operations_total",
    "Total appointment bookings",
    ["status"],
    registry=metrics_registry,
)


@router.get("/metrics")
def get_metrics():
    """Prometheus scrape endpoint."""
    return Response(
        content=generate_latest(metrics_registry),
        media_type=CONTENT_TYPE_LATEST
    )
