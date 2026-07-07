from django.conf import settings


def captcha_enabled() -> bool:
    return settings.CAPTCHA_ENABLED


def hr_sync_enabled() -> bool:
    return settings.HR_SYNC_ENABLED


def photo_moderation_email_enabled() -> bool:
    return settings.PHOTO_MODERATION_EMAIL_ENABLED
