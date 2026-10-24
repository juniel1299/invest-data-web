"""Django settings. 값은 환경 변수(.env)에서 읽는다."""

from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-change-me-in-dotenv-file")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "corsheaders",
    "apps.accounts",
    "apps.securities",
    "apps.market",
    "apps.portfolio",
    "apps.trades",
    "apps.digest",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Docker에서는 PostgreSQL, 아무 설정 없이 실행하면 SQLite
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Flutter 웹은 다른 포트에서 뜨므로 API 호출을 허용한다
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(localhost|127\.0\.0\.1):\d+$"] if DEBUG else []

# Celery: 미국 장 시간 기준으로 일정을 잡는다
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TIMEZONE = "America/New_York"
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
    "sync-securities-daily": {
        "task": "apps.securities.tasks.sync_securities_task",
        "schedule": crontab(hour=5, minute=0),
    },
    # 장 마감(16:00) 후 종가와 환율 갱신
    "update-market-data": {
        "task": "apps.market.tasks.update_market_data_task",
        "schedule": crontab(hour=16, minute=30, day_of_week="mon-fri"),
    },
    # FRED는 지수 값을 장 마감 몇 시간 뒤에 올린다
    "update-macro": {
        "task": "apps.market.tasks.update_macro_task",
        "schedule": crontab(hour=19, minute=0, day_of_week="mon-fri"),
    },
    "update-news": {
        "task": "apps.market.tasks.update_news_task",
        "schedule": crontab(minute=10),
    },
    "update-calendar": {
        "task": "apps.market.tasks.update_calendar_task",
        "schedule": crontab(hour=6, minute=0),
    },
    # 13F는 분기마다 몰려 나오지만 하루 한 번 확인해도 충분하다
    "update-13f": {
        "task": "apps.trades.tasks.update_13f_task",
        "schedule": crontab(hour=8, minute=0),
    },
    # ARK는 장 마감 후 저녁에 다음 날 기준 보유 파일을 올린다
    "update-ark": {
        "task": "apps.trades.tasks.update_ark_task",
        "schedule": crontab(hour=21, minute=0, day_of_week="mon-fri"),
    },
    "update-insiders": {
        "task": "apps.trades.tasks.update_insiders_task",
        "schedule": crontab(minute=20, hour="*/2"),
    },
    "update-congress": {
        "task": "apps.trades.tasks.update_congress_task",
        "schedule": crontab(minute=40, hour="7,13,19"),
    },
    # 장 마감 요약 이메일: 평소 17:00, 조기 마감일(13:00 마감)은 14:00. 휴장일은 작업 안에서 건너뛴다
    "send-daily-summary": {
        "task": "apps.digest.tasks.send_daily_summaries_task",
        "schedule": crontab(hour=17, minute=0, day_of_week="mon-fri"),
        "kwargs": {"kind": "regular"},
    },
    "send-daily-summary-early": {
        "task": "apps.digest.tasks.send_daily_summaries_task",
        "schedule": crontab(hour=14, minute=0, day_of_week="mon-fri"),
        "kwargs": {"kind": "early"},
    },
    "update-fundamentals": {
        "task": "apps.market.tasks.update_fundamentals_task",
        "schedule": crontab(hour=7, minute=0, day_of_week="sun"),
    },
}

# SEC는 요청마다 이름과 연락처가 담긴 User-Agent를 요구한다
SEC_USER_AGENT = env("SEC_USER_AGENT", default="invest-data-web dev@example.com")

# 종가 출처: stooq(키 불필요) 또는 tiingo(무료 키 필요)
PRICE_PROVIDER = env("PRICE_PROVIDER", default="stooq")
TIINGO_API_KEY = env("TIINGO_API_KEY", default="")
# 실적 발표일(Finnhub)과 배당 일정(Alpha Vantage). 둘 다 무료 키. 없으면 그 일정만 빠진다
FINNHUB_API_KEY = env("FINNHUB_API_KEY", default="")
ALPHA_VANTAGE_API_KEY = env("ALPHA_VANTAGE_API_KEY", default="")

# 푸시 알림: ntfy (무료). 직접 띄운 ntfy 서버가 있으면 주소를 바꾼다
NTFY_SERVER = env("NTFY_SERVER", default="https://ntfy.sh")
# 13F의 CUSIP을 티커로 바꿀 때 쓴다. 키 없이도 되지만 무료 키가 있으면 빠르다
OPENFIGI_API_KEY = env("OPENFIGI_API_KEY", default="")

# 이메일: 기본은 콘솔 출력. Gmail은 앱 비밀번호로 smtp+tls://아이디%40gmail.com:앱비밀번호@smtp.gmail.com:587
EMAIL_CONFIG = env.email_url_config(env("EMAIL_URL", default="") or "consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="") or "미국 주식 모음 <noreply@localhost>"
# 이메일 속 '앱 열기' 링크
APP_URL = env("APP_URL", default="") or "http://localhost:8080"
