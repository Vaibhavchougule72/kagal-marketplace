from pathlib import Path
import os
from decouple import config
import dj_database_url
import cloudinary

# ========================
# BASE
# ========================
BASE_DIR = Path(__file__).resolve().parent.parent

OTP_ENABLED = False

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = [
    "kagal-marketplace.onrender.com",
    "loka-store.online",
    "www.loka-store.online"
]

CSRF_TRUSTED_ORIGINS = [
    "https://loka-store.online",
    "https://www.loka-store.online"
]

# ========================
# APPS
# ========================
INSTALLED_APPS = [
    'marketplace.apps.MarketplaceConfig',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    "csp",
]

# ========================
# MIDDLEWARE
# ========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'csp.middleware.CSPMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'marketplace.middleware.ForceMarathiMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',

    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.gzip.GZipMiddleware',

    'marketplace.middleware.PermissionsPolicyMiddleware',
]

ROOT_URLCONF = 'config.urls'

# ========================
# TEMPLATES
# ========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'marketplace.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ========================
# DATABASE
# ========================
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR}/db.sqlite3",
        conn_max_age=600
    )
}

# ========================
# PASSWORD VALIDATION
# ========================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========================
# INTERNATIONALIZATION
# ========================
LANGUAGE_CODE = 'mr'

LANGUAGES = [
    ('en', 'English'),
    ('mr', 'Marathi'),
]

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True
USE_TZ = True

# ========================
# STATIC FILES
# ========================
STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MAX_AGE = 31536000

# ========================
# LOGIN
# ========================
LOGIN_URL = '/dashboard-login/'

# ========================
# RAZORPAY
# ========================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# ========================
# REDIS
# ========================
REDIS_URL = os.environ.get("REDIS_URL")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# ========================
# CLOUDINARY
# ========================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# ========================
# SECURITY
# ========================
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

X_FRAME_OPTIONS = "DENY"

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ========================
# CSP (NEW FORMAT - FIXED)
# ========================
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),

        # ✅ Scripts (main)
        "script-src": (
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            "https://checkout.razorpay.com",
            "https://cdn.jsdelivr.net",
            "blob:",
        ),

        # 🔥 THIS IS YOUR MAIN FIX
        "script-src-elem": (
            "'self'",
            "'unsafe-inline'",
            "https://checkout.razorpay.com",
            "https://cdn.jsdelivr.net",
            "blob:",   # ✅ ADD THIS
        ),

        # ✅ Styles
        "style-src": (
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
            "https://cdn.jsdelivr.net",
        ),

        "style-src-elem": (
            "'self'",
            "'unsafe-inline'",
            "https://fonts.googleapis.com",
            "https://cdn.jsdelivr.net",
        ),

        # ✅ Fonts
        "font-src": (
            "'self'",
            "https://fonts.gstatic.com",
        ),

        # ✅ Images
        "img-src": (
            "'self'",
            "data:",
            "https://res.cloudinary.com",
            "https:",
        ),

        # ✅ API
        "connect-src": (
            "'self'",
            "https://api.razorpay.com",
            "https://cdn.jsdelivr.net",
        ),

        # ✅ Razorpay iframe
        "frame-src": (
            "'self'",
            "https://checkout.razorpay.com",
        ),
    }
}
# ========================
# LOCALE
# ========================
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]