"""CyJob ayarları: personel + işveren portalı tek projede (yayına almadan önce README'deki notlara bak)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Yayına alırken DJANGO_SECRET_KEY ortam değişkeni ile gerçek bir anahtar ver.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "gelistirme-icin-gecici-anahtar-yayinda-degistir"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "portal",  # ana sayfa, ortak tema, logo (admin şablonunu ezmesi için en üstte)
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",  # işveren portalı
    "jobs",                  # personel (iş arayan) portalı
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "jobs.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "Asia/Nicosia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Her portalın kendi giriş sayfası var; buradaki değerler yedek davranıştır.
LOGIN_URL = "home"
LOGIN_REDIRECT_URL = "employer:dashboard"
LOGOUT_REDIRECT_URL = "home"

# Oturum / çerez güvenliği
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 12  # 12 saat
CSRF_COOKIE_HTTPONLY = False
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Personel CV dosyaları
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
