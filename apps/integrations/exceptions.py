from apps.common.exceptions import ApplicationError


class HrIntegrationError(ApplicationError):
    status_code = 503
    code = "hr_integration_error"
    default_detail = "HR integration is unavailable."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class HrSyncDisabledError(HrIntegrationError):
    code = "hr_sync_disabled"
    status_code = 503
    default_detail = "HR sync is disabled."


class HrValidationError(HrIntegrationError):
    code = "hr_validation_error"
    status_code = 400
    default_detail = "HR rejected the sync request."


class HrEmployeeLockedError(HrIntegrationError):
    code = "hr_employee_locked"
    status_code = 423
    default_detail = "Employee is locked in HR."


class HrUpstreamError(HrIntegrationError):
    code = "hr_upstream_error"
    status_code = 502
    default_detail = "HR service returned an upstream error."


class HrTimeoutError(HrIntegrationError):
    code = "hr_timeout"
    status_code = 504
    default_detail = "HR service timed out."


class CaptchaValidationError(ApplicationError):
    default_detail = "Captcha verification failed."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class CaptchaUnavailableError(ApplicationError):
    default_detail = "Captcha verification is unavailable."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)
