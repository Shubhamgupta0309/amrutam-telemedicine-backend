import json
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.modules.audit.models import AuditLog
from app.core.logging import logger, correlation_id_ctx


SENSITIVE_FIELD_NAMES = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "secret_key", "authorization", "mfa_secret", "credit_card",
    "cvv", "payment_token"
}


def sanitize_dict(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize data by removing or masking sensitive fields."""
    if not data:
        return {}
    sanitized = {}
    for k, v in data.items():
        if k.lower() in SENSITIVE_FIELD_NAMES:
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        else:
            sanitized[k] = v
    return sanitized


def record_audit_log(
    db: Session,
    action: str,
    resource_type: str,
    actor_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Append-only audit logger. Ensures no secrets or sensitive credentials are ever written.
    """
    clean_details = sanitize_dict(details)
    req_id = request_id or correlation_id_ctx.get()

    audit_entry = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=req_id,
        ip_address=ip_address,
        details=json.dumps(clean_details) if clean_details else None,
    )
    db.add(audit_entry)
    # Note: caller will commit as part of their business transaction or separate flush
    logger.info(
        f"Audit: {action} on {resource_type}:{resource_id} by {actor_id or 'anonymous'}",
        extra={"action": action, "resource_type": resource_type, "actor_id": actor_id}
    )
    return audit_entry
