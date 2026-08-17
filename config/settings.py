from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-secret-key-change-me")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "django_celery_beat",
    "servers_app",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Defaults to SQLite for zero-friction local dev; point DATABASE_URL-style vars at
# Postgres in real deployments (see docker-compose.yml at the repo root).
DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.sqlite3"),
        "NAME": config("DB_NAME", default=BASE_DIR / "db.sqlite3"),
        "USER": config("DB_USER", default=""),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default=""),
        "PORT": config("DB_PORT", default=""),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# The Vite build for the React frontend outputs here (frontend/vite.config.js
# build.outDir points at ../static/react). runserver serves it automatically in DEBUG
# mode with no extra step; run `collectstatic` before deploying behind a real web server.
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PERMISSION_CLASSES": [],
}

CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool)  # tighten before production

# --- Celery ---
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --- App-specific settings ---
ADMIN_API_KEY = config("ADMIN_API_KEY", default="dev-admin-key-change-me")
OWNER_LINK_SECRET = config("OWNER_LINK_SECRET", default="dev-owner-link-secret-change-me")
OWNER_LINK_MAX_AGE_SECONDS = config("OWNER_LINK_MAX_AGE_SECONDS", default=60 * 60 * 24 * 30, cast=int)
FRONTEND_BASE_URL = config("FRONTEND_BASE_URL", default="http://localhost:8000")

EMAIL_HOST = config("SMTP_HOST", default="")
EMAIL_PORT = config("SMTP_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("SMTP_USERNAME", default="")
EMAIL_HOST_PASSWORD = config("SMTP_PASSWORD", default="")
EMAIL_USE_TLS = config("SMTP_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("SMTP_FROM_ADDRESS", default="infra-ops@company.com")
# If EMAIL_HOST is blank, fall back to console backend so reminders are visible in dev logs.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"

DEFAULT_CPU_THRESHOLD = config("DEFAULT_CPU_THRESHOLD", default=20, cast=float)
DEFAULT_MEMORY_THRESHOLD = config("DEFAULT_MEMORY_THRESHOLD", default=25, cast=float)
DEFAULT_STORAGE_THRESHOLD = config("DEFAULT_STORAGE_THRESHOLD", default=30, cast=float)
DEFAULT_RULE_MODE = config("DEFAULT_RULE_MODE", default="any")
OVERUTILIZED_CEILING = config("OVERUTILIZED_CEILING", default=85, cast=float)
