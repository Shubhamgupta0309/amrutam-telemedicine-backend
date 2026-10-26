import json
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.session import SessionLocal
from app.modules.bookings.models import OutboxEvent


def process_event(event: OutboxEvent) -> bool:
    """
    Simulate processing of domain events (e.g. sending push/SMS notifications,
    dispatching webhooks, or syncing with third-party hospital EHR).
    """
    data = json.loads(event.payload)
    logger.info(
        f"Processing Outbox Event [{event.event_type}]: id={event.id}",
        extra={"event_type": event.event_type, "event_id": event.id}
    )

    if event.event_type == "BOOKING_CONFIRMED":
        # Simulate SMS dispatch to patient and doctor
        logger.info(f"Notification sent for booking: {data.get('consultation_id')}")
        return True
    elif event.event_type == "BOOKING_CANCELLED":
        logger.info(f"Cancellation alert sent for consultation: {data.get('consultation_id')}")
        return True
    elif event.event_type == "PRESCRIPTION_ISSUED":
        logger.info(f"Prescription dispatch notification for patient: {data.get('patient_id')}")
        return True
    elif event.event_type == "PAYMENT_PROCESSED":
        logger.info(f"Payment receipt email dispatched for payment: {data.get('payment_id')}")
        return True

    return True


def run_outbox_batch(db: Session, limit: int = 50) -> int:
    """Process a single batch of pending outbox events."""
    events = list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "PENDING")
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
        ).all()
    )

    processed_count = 0
    for event in events:
        try:
            success = process_event(event)
            if success:
                event.status = "PROCESSED"
                event.processed_at = datetime.now(timezone.utc)
                processed_count += 1
        except Exception as exc:
            event.retry_count += 1
            event.last_error = str(exc)
            if event.retry_count >= event.max_retries:
                event.status = "FAILED"
            logger.error(f"Failed processing event {event.id}: {exc}")

    db.commit()
    return processed_count


def start_worker_loop(interval_seconds: float = 5.0, max_iterations: int = 0):
    """Run worker daemon or test loop."""
    logger.info("Starting Outbox Event Worker...")
    iterations = 0
    while True:
        db = SessionLocal()
        try:
            count = run_outbox_batch(db)
            if count > 0:
                logger.info(f"Outbox worker processed {count} events.")
        except Exception as e:
            logger.error(f"Error in outbox worker loop: {e}")
        finally:
            db.close()

        iterations += 1
        if max_iterations > 0 and iterations >= max_iterations:
            break

        time.sleep(interval_seconds)


if __name__ == "__main__":
    start_worker_loop()
