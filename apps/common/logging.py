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
