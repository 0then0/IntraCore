import io
import json
import logging

from apps.common.logging import (
    JsonFormatter,
    RequestIdFilter,
    mask_sensitive_mapping,
    request_id_context,
)


def test_mask_sensitive_mapping_masks_nested_values():
    masked = mask_sensitive_mapping(
        {
            "department_code": "engineering",
            "profile": {
                "email": "employee@example.com",
                "phone": "+79990001122",
            },
            "contacts": [
                {
                    "telegram_username": "employee",
                    "kind": "telegram",
                },
            ],
        },
    )

    assert masked == {
        "department_code": "engineering",
        "profile": {
            "email": "***",
            "phone": "***",
        },
        "contacts": [
            {
                "telegram_username": "***",
                "kind": "telegram",
            },
        ],
    }


def test_json_formatter_includes_structured_masked_fields_and_request_id():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    logger = logging.getLogger("tests.structured")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    context_token = request_id_context.set("request-id-123")

    try:
        logger.info(
            "hr.employee.response",
            extra={
                "event": "hr.employee.response",
                "duration_ms": 12,
                "masked_payload": {"email": "***"},
            },
        )
    finally:
        request_id_context.reset(context_token)
        logger.handlers = []

    payload = json.loads(stream.getvalue())
    assert payload["request_id"] == "request-id-123"
    assert payload["event"] == "hr.employee.response"
    assert payload["duration_ms"] == 12
    assert payload["masked_payload"] == {"email": "***"}
