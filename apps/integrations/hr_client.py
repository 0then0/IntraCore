import json
import logging
import os
from math import isfinite
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from apps.common.logging import mask_sensitive_mapping
from apps.integrations.exceptions import (
    HrEmployeeLockedError,
    HrIntegrationError,
    HrTimeoutError,
    HrUpstreamError,
    HrValidationError,
)

DEFAULT_HR_API_BASE_URL = "http://hr.example.test"
DEFAULT_HR_API_TIMEOUT_SECONDS = 5.0

logger = logging.getLogger(__name__)


class HrClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        opener=urlopen,
    ):
        self.base_url = (
            base_url or os.environ.get("HR_API_BASE_URL") or DEFAULT_HR_API_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = _timeout_seconds(timeout_seconds)
        self._opener = opener

    def get_employee(self, external_id: str) -> dict:
        masked_request = mask_sensitive_mapping({"external_id": external_id})
        logger.info(
            "hr.employee.request",
            extra={
                "event": "hr.employee.request",
                "masked_payload": masked_request,
            },
        )

        request = Request(
            f"{self.base_url}/employees/{quote(external_id, safe='')}/",
            headers={"Accept": "application/json"},
            method="GET",
        )
        started_at = perf_counter()

        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                payload = _decode_json_response(response.read())
        except HrUpstreamError:
            self._log_upstream_error(started_at)
            raise
        except HTTPError as error:
            self._handle_http_error(error)
        except TimeoutError:
            self._log_timeout(started_at)
            raise HrTimeoutError() from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                self._log_timeout(started_at)
                raise HrTimeoutError() from None

            self._log_upstream_error(started_at)
            raise HrUpstreamError() from None

        if not isinstance(payload, dict):
            self._log_upstream_error(started_at)
            raise HrUpstreamError("HR response payload was invalid.")

        logger.info(
            "hr.employee.response",
            extra={
                "event": "hr.employee.response",
                "duration_ms": _duration_ms(started_at),
                "masked_payload": mask_sensitive_mapping(payload),
            },
        )

        return payload

    def _handle_http_error(self, error: HTTPError) -> None:
        status_code = error.code
        logger.warning(
            "hr.employee.error",
            extra={
                "event": "hr.employee.error",
                "upstream_status": status_code,
            },
        )

        if status_code == 400:
            raise HrValidationError() from None
        if status_code == 423:
            raise HrEmployeeLockedError() from None
        if status_code >= 500:
            raise HrUpstreamError() from None

        raise HrUpstreamError("HR service returned an unexpected status.") from None

    def _log_timeout(self, started_at: float) -> None:
        logger.warning(
            "hr.employee.timeout",
            extra={
                "event": "hr.employee.timeout",
                "duration_ms": _duration_ms(started_at),
            },
        )

    def _log_upstream_error(self, started_at: float) -> None:
        logger.warning(
            "hr.employee.upstream_error",
            extra={
                "event": "hr.employee.upstream_error",
                "duration_ms": _duration_ms(started_at),
            },
        )


def _timeout_seconds(timeout_seconds: float | None) -> float:
    if timeout_seconds is None:
        raw_timeout_seconds = os.environ.get(
            "HR_API_TIMEOUT_SECONDS",
            str(DEFAULT_HR_API_TIMEOUT_SECONDS),
        )
        try:
            timeout_seconds = float(raw_timeout_seconds)
        except ValueError:
            raise HrIntegrationError(
                "HR API timeout config is invalid.",
            ) from None

    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise HrIntegrationError("HR API timeout must be greater than zero.")

    return timeout_seconds


def _decode_json_response(body: bytes) -> object:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HrUpstreamError("HR response body was invalid JSON.") from None


def _duration_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
