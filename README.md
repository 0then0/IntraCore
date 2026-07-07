# IntraCore

Production-like Django backend project for practicing internal employee portal features.

## Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- Celery
- Redis
- pytest
- drf-spectacular
- ruff
- uv

## Local environment

Copy the example environment file and adjust values if needed:

```bash
cp .env.example .env
```

## Docker commands

```bash
docker compose up --build
docker compose down
docker compose down -v
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web pytest
docker compose exec web ruff check .
docker compose exec web ruff format .
```

## Local run with uv

Use this mode when PostgreSQL and Redis are available on the host machine.

```bash
cp .env.example .env
uv sync
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver
uv run --env-file .env celery -A config worker --loglevel=info
```

## uv quality commands

Use the same local environment file:

```bash
uv run --env-file .env pytest
uv run --env-file .env ruff check .
uv run --env-file .env ruff format .
```

## API docs

After starting the app:

- OpenAPI schema: `http://localhost:8000/api/schema/`
- Swagger UI: `http://localhost:8000/api/docs/`
- Health check: `http://localhost:8000/health/`
- Wagtail admin: `http://localhost:8000/cms/`

## Core profile API

Employee API identifiers use `employee_uuid`, exposed as `id` in responses.

- `GET /api/profile/me/`
- `PATCH /api/profile/me/`
- `GET /api/employees/{id}/`
- `PATCH /api/admin/employees/{id}/`

Hidden phone and birthdate values are visible only to the profile owner. Nested
employee objects apply the same privacy rule independently.

Admin employee updates accept `department` by department `code`, and `manager`
or `hrbp` by employee UUID.

## Photo moderation API

Uploaded profile photos are stored as pending photos until an admin approves
them. Pending photos are visible to the profile owner and moderation admins,
but are not exposed as current public photos.

- `POST /api/profile/me/photo/`
- `GET /api/admin/photo-moderation/`
- `POST /api/admin/photo-moderation/{employee_id}/approve/`
- `POST /api/admin/photo-moderation/{employee_id}/reject/`

Rejected photo email notifications are sent by Celery only when
`PHOTO_MODERATION_EMAIL_ENABLED=true`.

## Wagtail content API

Legal documents are managed as Wagtail snippets linked to Wagtail documents.

- `GET /api/legal-documents/`

Onboarding items are managed as Wagtail snippets. Viewed onboarding records are
stored per employee and protected by a database uniqueness constraint.

- `GET /api/onboarding/available/`
- `POST /api/onboarding/{code}/viewed/`

Anonymous onboarding requests return `401`.
