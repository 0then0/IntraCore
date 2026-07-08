import logging
from io import BytesIO
from urllib.error import HTTPError

import pytest

from apps.integrations.exceptions import (
    HrEmployeeLockedError,
    HrIntegrationError,
    HrTimeoutError,
    HrUpstreamError,
    HrValidationError,
)
from apps.integrations.hr_client import HrClient


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self.body


def http_error(status_code: int) -> HTTPError:
    return HTTPError(
        url="http://hr.test/employees/hr-1/",
        code=status_code,
        msg="upstream error",
        hdrs=None,
        fp=BytesIO(b'{"email": "secret@example.com"}'),
    )


def test_hr_client_uses_timeout_and_returns_payload():
    calls = {}

    def opener(request, *, timeout):
        calls["url"] = request.full_url
        calls["timeout"] = timeout
        return FakeResponse(
            b'{"external_id": "hr-1", "email": "employee@example.com"}',
        )

    client = HrClient(
        base_url="http://hr.test",
        timeout_seconds=2.5,
        opener=opener,
    )

    payload = client.get_employee("hr-1")

    assert calls == {
        "url": "http://hr.test/employees/hr-1/",
        "timeout": 2.5,
    }
    assert payload["external_id"] == "hr-1"


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, HrValidationError),
        (423, HrEmployeeLockedError),
        (500, HrUpstreamError),
    ],
)
def test_hr_client_maps_known_http_errors(status_code, expected_error):
    def opener(request, *, timeout):
        raise http_error(status_code)

    client = HrClient(base_url="http://hr.test", opener=opener)

    with pytest.raises(expected_error) as error:
        client.get_employee("hr-1")

    assert error.value.__cause__ is None


def test_hr_client_maps_timeout():
    def opener(request, *, timeout):
        raise TimeoutError()

    client = HrClient(base_url="http://hr.test", opener=opener)

    with pytest.raises(HrTimeoutError) as error:
        client.get_employee("hr-1")

    assert error.value.__cause__ is None


def test_hr_client_rejects_invalid_env_timeout(mocker):
    mocker.patch.dict("os.environ", {"HR_API_TIMEOUT_SECONDS": "invalid"})

    with pytest.raises(HrIntegrationError) as error:
        HrClient(base_url="http://hr.test")

    assert str(error.value) == "HR API timeout config is invalid."


@pytest.mark.parametrize("timeout_seconds", [0, -1, float("nan"), float("inf")])
def test_hr_client_rejects_invalid_timeout_values(timeout_seconds):
    with pytest.raises(HrIntegrationError) as error:
        HrClient(base_url="http://hr.test", timeout_seconds=timeout_seconds)

    assert str(error.value) == "HR API timeout must be greater than zero."


def test_hr_client_logs_masked_payloads(caplog):
    def opener(request, *, timeout):
        return FakeResponse(
            b"{"
            b'"external_id": "hr-secret",'
            b'"email": "secret@example.com",'
            b'"login": "secret-login",'
            b'"phone": "+79990001122",'
            b'"department_code": "engineering"'
            b"}",
        )

    caplog.set_level(logging.INFO, logger="apps.integrations.hr_client")
    client = HrClient(base_url="http://hr.test", opener=opener)

    client.get_employee("hr-secret")

    masked_payloads = [
        record.__dict__.get("masked_payload")
        for record in caplog.records
        if record.__dict__.get("masked_payload")
    ]
    assert masked_payloads
    assert "secret@example.com" not in str(masked_payloads)
    assert "secret-login" not in str(masked_payloads)
    assert "hr-secret" not in str(masked_payloads)
    assert "+79990001122" not in str(masked_payloads)
    assert masked_payloads[-1]["department_code"] == "engineering"
