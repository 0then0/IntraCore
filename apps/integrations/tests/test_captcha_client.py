import json

import pytest

from apps.integrations.captcha_client import CaptchaClient
from apps.integrations.exceptions import CaptchaUnavailableError, CaptchaValidationError


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.body


def test_captcha_client_uses_timeout_and_accepts_successful_response():
    calls = {}

    def opener(request, *, timeout):
        calls["timeout"] = timeout
        calls["body"] = request.data
        return FakeResponse(b'{"success": true}')

    client = CaptchaClient(
        verify_url="http://captcha.test/verify",
        timeout_seconds=2.5,
        opener=opener,
    )

    client.verify("token-value")

    assert calls == {"timeout": 2.5, "body": b"token=token-value"}


def test_captcha_client_rejects_unsuccessful_response():
    client = CaptchaClient(
        verify_url="http://captcha.test/verify",
        opener=lambda request, *, timeout: FakeResponse(
            json.dumps({"success": False}).encode(),
        ),
    )

    with pytest.raises(CaptchaValidationError):
        client.verify("token-value")


def test_captcha_client_maps_timeout_to_controlled_error():
    def opener(request, *, timeout):
        raise TimeoutError()

    client = CaptchaClient(verify_url="http://captcha.test/verify", opener=opener)

    with pytest.raises(CaptchaUnavailableError):
        client.verify("token-value")
