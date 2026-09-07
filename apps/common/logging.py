import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

SENSITIVE_LOG_FIELDS = {
    "birthdate",
    "city",
    "email",
    "external_id",
    "first_name",
    "last_name",
    "login",
    "middle_name",
    "password",
    "phone",
    "telegram_username",
    "token",
}

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }

        for field_name in ("event", "duration_ms", "upstream_status", "masked_payload"):
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value

        return json.dumps(payload, default=str, sort_keys=True)


def mask_sensitive_mapping(payload: dict) -> dict:
    masked = {}

    for key, value in payload.items():
        if key in SENSITIVE_LOG_FIELDS:
            masked[key] = "***"
            continue

        masked[key] = _mask_sensitive_value(value)

    return masked


def _mask_sensitive_value(value):
    if isinstance(value, dict):
        return mask_sensitive_mapping(value)

    if isinstance(value, list):
        return [_mask_sensitive_value(item) for item in value]

    return value
