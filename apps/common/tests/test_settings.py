import pytest
from config.settings.base import _env_positive_int, _secret_key
from django.core.exceptions import ImproperlyConfigured


def test_secret_key_is_required_when_debug_is_disabled(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    with pytest.raises(ImproperlyConfigured):
        _secret_key(debug=False)


def test_secret_key_has_local_default_when_debug_is_enabled(monkeypatch):
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    assert _secret_key(debug=True) == "unsafe-test-secret-key"


@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_positive_integer_environment_value_is_validated(monkeypatch, value):
    monkeypatch.setenv("TEST_POSITIVE_INTEGER", value)

    with pytest.raises(ImproperlyConfigured):
        _env_positive_int("TEST_POSITIVE_INTEGER", default=1)
