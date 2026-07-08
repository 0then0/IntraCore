import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name)

    if value is None:
        if required:
            raise ImproperlyConfigured(f"Environment variable {name} is required.")
        if default is None:
            return ""
        return default

    return value


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)

    if value is None:
        return default

    return value.lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, *, default: list[str] | None = None) -> list[str]:
    value = os.environ.get(name)

    if value is None:
        return default or []

    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = _env("DJANGO_SECRET_KEY", default="unsafe-test-secret-key")
DEBUG = _env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "rest_framework",
    "apps.common",
    "drf_spectacular",
    "apps.employees",
    "apps.legal",
    "apps.onboarding",
    "apps.org",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.common.middleware.RequestIdMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _env("POSTGRES_DB", "intracore"),
        "USER": _env("POSTGRES_USER", "intracore"),
        "PASSWORD": _env("POSTGRES_PASSWORD", "intracore"),
        "HOST": _env("POSTGRES_HOST", "localhost"),
        "PORT": _env("POSTGRES_PORT", "5432"),
    },
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
WAGTAIL_SITE_NAME = "IntraCore"
WAGTAILADMIN_BASE_URL = _env(
    "WAGTAILADMIN_BASE_URL",
    "http://localhost:8000/cms",
)


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultPageNumberPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "PAGE_SIZE": int(_env("DRF_PAGE_SIZE", "20")),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "IntraCore API",
    "DESCRIPTION": "Backend API for the IntraCore internal employee portal.",
    "VERSION": "0.1.0",
    "SERVE_URLCONF": "config.api_urls",
    "SERVE_INCLUDE_SCHEMA": False,
}


REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(_env("CELERY_TASK_TIME_LIMIT", "300"))


EMAIL_BACKEND = _env(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = _env("DJANGO_DEFAULT_FROM_EMAIL", "noreply@intracore.local")


CAPTCHA_ENABLED = _env_bool("CAPTCHA_ENABLED", default=False)
HR_SYNC_ENABLED = _env_bool("HR_SYNC_ENABLED", default=False)
PHOTO_MODERATION_EMAIL_ENABLED = _env_bool(
    "PHOTO_MODERATION_EMAIL_ENABLED",
    default=False,
)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _env("DJANGO_LOG_LEVEL", "INFO"),
    },
}
