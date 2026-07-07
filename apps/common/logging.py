SENSITIVE_LOG_FIELDS = {
    "birthdate",
    "email",
    "first_name",
    "last_name",
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

        masked[key] = value

    return masked
