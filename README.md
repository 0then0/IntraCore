# Internal Portal Lab

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
