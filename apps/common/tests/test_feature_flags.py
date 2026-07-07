import pytest

from apps.common.feature_flags import (
    captcha_enabled,
    hr_sync_enabled,
    photo_moderation_email_enabled,
)


@pytest.mark.parametrize(
    ("setting_name", "flag_function"),
    [
        ("CAPTCHA_ENABLED", captcha_enabled),
        ("HR_SYNC_ENABLED", hr_sync_enabled),
        ("PHOTO_MODERATION_EMAIL_ENABLED", photo_moderation_email_enabled),
    ],
)
def test_feature_flag_helpers_return_enabled_value(
    settings,
    setting_name,
    flag_function,
):
    setattr(settings, setting_name, True)

    assert flag_function() is True


@pytest.mark.parametrize(
    ("setting_name", "flag_function"),
    [
        ("CAPTCHA_ENABLED", captcha_enabled),
        ("HR_SYNC_ENABLED", hr_sync_enabled),
        ("PHOTO_MODERATION_EMAIL_ENABLED", photo_moderation_email_enabled),
    ],
)
def test_feature_flag_helpers_return_disabled_value(
    settings,
    setting_name,
    flag_function,
):
    setattr(settings, setting_name, False)

    assert flag_function() is False
