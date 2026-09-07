# Observability and API Error Notes

## Health

`GET /health/` is public and returns a small process health response:

```json
{ "status": "ok" }
```

The endpoint intentionally avoids external I/O and heavy database checks. Use it
for container/process liveness, not as a full dependency readiness probe.

## Request IDs

Every response includes `X-Request-ID`.

- If the client sends `X-Request-ID`, the same value is returned.
- If the header is missing, the middleware generates a UUID.
- Incoming values longer than 128 characters, or containing CR/LF, are ignored
  and replaced with a generated UUID.
- The value is available on the request object as `request.request_id`.

The JSON log formatter adds this ID to records emitted while processing an HTTP
request. Celery task records have a `null` request ID unless a task-specific
correlation ID is added by the caller.

## Error Mapping

Standard DRF errors keep the normal DRF response shape:

- `401`: unauthenticated request.
- `403`: authenticated user without permission.
- `404`: requested object was not found.
- `400`: serializer or business validation failure.

Custom business errors that return a controlled body use:

```json
{
  "code": "stable_machine_code",
  "detail": "Human readable message."
}
```

Current custom mappings:

- `POST /api/admin/employees/{id}/hr-sync/`
  - `400 employee_external_id_missing`: employee has no external HR id.
  - `503 hr_sync_disabled`: `HR_SYNC_ENABLED=false`.

External HR client mappings in the service/task layer:

- upstream `400` -> `HrValidationError`;
- upstream `423` -> `HrEmployeeLockedError`;
- upstream `500+` -> `HrUpstreamError`;
- timeout -> `HrTimeoutError`.

The admin API queues HR sync work and does not call the external HR service in
the request-response cycle, so upstream `400`, `423`, `500+`, and timeout errors
are task/service outcomes, not direct HTTP responses from the queue endpoint.

When `CAPTCHA_ENABLED=true`, `POST /api/profile/me/photo/` returns `400` for a
missing or rejected `captcha_token` and `503 captcha_unavailable` when the
verification service cannot be reached.

## Sensitive Logs

External HR logs are JSON records with `event`, `request_id`, `duration_ms`,
`upstream_status`, and `masked_payload` fields when applicable. Sensitive keys
such as email, phone, names, login, external id, city, birthdate, Telegram
username, password, and token are masked recursively.

Do not log raw HR payloads or raw request bodies.

## OpenAPI Review

OpenAPI is generated with drf-spectacular at:

- `GET /api/schema/`
- `GET /api/docs/`

The schema is scoped to the public API URLConf. Wagtail admin/document routes
remain available at runtime but are intentionally excluded from OpenAPI.
The project-level `spectacular` management command uses the same API URLConf by
default, so schema validation commands do not scan Wagtail admin routes.

Schema annotations should document only real status codes. For custom error
bodies, use `CodeDetailErrorSerializer`. For ordinary DRF validation errors,
prefer descriptions unless the endpoint has a stable explicit error body.
