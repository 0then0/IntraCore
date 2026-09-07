import json
import os
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from apps.integrations.exceptions import CaptchaUnavailableError, CaptchaValidationError

DEFAULT_CAPTCHA_VERIFY_URL = "http://captcha.example.test/verify"
DEFAULT_CAPTCHA_TIMEOUT_SECONDS = 5.0


class CaptchaClient:
    def __init__(
        self,
        *,
        verify_url: str | None = None,
        timeout_seconds: float | None = None,
        opener=urlopen,
    ):
        self.verify_url = (
            verify_url
            or os.environ.get("CAPTCHA_VERIFY_URL")
            or DEFAULT_CAPTCHA_VERIFY_URL
        )
        self.timeout_seconds = _timeout_seconds(timeout_seconds)
        self._opener = opener

    def verify(self, token: str) -> None:
        request = Request(
            self.verify_url,
            data=urlencode({"token": token}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                payload = _decode_response(response.read())
        except HTTPError as error:
            if error.code == 400:
                raise CaptchaValidationError() from None
            raise CaptchaUnavailableError() from None
        except (TimeoutError, URLError):
            raise CaptchaUnavailableError() from None

        if payload.get("success") is not True:
            raise CaptchaValidationError()


def _timeout_seconds(timeout_seconds: float | None) -> float:
    if timeout_seconds is None:
        raw_timeout = os.environ.get(
            "CAPTCHA_TIMEOUT_SECONDS",
            str(DEFAULT_CAPTCHA_TIMEOUT_SECONDS),
        )
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError:
            raise CaptchaUnavailableError(
                "Captcha timeout config is invalid."
            ) from None

    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise CaptchaUnavailableError("Captcha timeout must be greater than zero.")

    return timeout_seconds


def _decode_response(body: bytes) -> dict:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CaptchaUnavailableError(
            "Captcha response body was invalid JSON."
        ) from None

    if not isinstance(payload, dict):
        raise CaptchaUnavailableError("Captcha response payload was invalid.")

    return payload
