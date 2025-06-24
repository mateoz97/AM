# restaurant_service/settings.py

import os
from pathlib import Path
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Cargar variables de entorno
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY and DEBUG is False:
    raise ImproperlyConfigured("SECRET_KEY must be set in environment variables for production")
elif not SECRET_KEY:
    SECRET_KEY = 'insecure-dev-key-do-not-use-in-production'
    print("WARNING: Using insecure development SECRET_KEY")

# ALLOWED_HOSTS = ['127.0.0.1:8000']

# Application definition
INSTALLED_APPS = [
    'daphne',  # Django Channels ASGI server
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'channels',  # Django Channels
    'app.accounts',
    'app.roles',
    'app.business',
    'app.core',
    'app.posts',
    'app.inventory',
    'app.settings',
    'app.orders',  # New orders app
]

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    # Agrega otros orígenes permitidos según sea necesario
]

CORS_ALLOW_CREDENTIALS = True


MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', 
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.BusinessMiddleware', 
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': os.getenv('ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DATABASE_NAME', 'bistartless_main'),
        'USER': os.getenv('USERNAME', 'bistartless-dev'),
        'PASSWORD': os.getenv('PASSWORD', ''),
        'HOST': os.getenv('HOST', 'localhost'),
        'PORT': os.getenv('PORT', '5432'),
        'OPTIONS': {
            # PostgreSQL specific options can go here if needed
        },
        'CONN_MAX_AGE': 600,
        'ATOMIC_REQUESTS': True,
    },
}

# Con PostgreSQL, usaremos esquemas separados para cada negocio en lugar de bases de datos separadas
# Esta funcionalidad se manejará dinámicamente en el router de base de datos

# Router para dirigir consultas a la base de datos correcta
DATABASE_ROUTERS = ['config.db_routers.BusinessRouter']

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

TIME_ZONE = 'America/Bogota'  # Ajusta a tu zona horaria

USE_I18N = True

USE_L10N = True

USE_TZ = True

LANGUAGES = [
    ('es', _('Spanish')),
    ('en', _('English')),
]
LANGUAGE_CODE = 'es'  # Idioma por defecto

LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]
# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Rest Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
    
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),  # Expira en 1 hora
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),  # Expira en 7 días
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv('JWT_SIGNING_KEY', SECRET_KEY),
}


AUTH_USER_MODEL = 'accounts.CustomUser'

# En config/settings.py

# Configuración de logs
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/django.log',
            'formatter': 'verbose',
        },
        'auth_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/auth.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'app.accounts': {
            'handlers': ['console', 'auth_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'app.multi_tenant': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Crear directorio de logs si no existe
if not os.path.exists(BASE_DIR / 'logs'):
    os.makedirs(BASE_DIR / 'logs')

# =====================================
# DJANGO CHANNELS CONFIGURATION
# =====================================

# ASGI application
ASGI_APPLICATION = 'config.asgi.application'

# Channel layers configuration (Redis backend with fallback)
# Configuración para diferentes entornos
def get_redis_config():
    """Configura Redis según el entorno (local, GCP, etc.)"""
    
    # Variables de entorno para Redis
    redis_url = os.getenv('REDIS_URL')
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD')
    redis_db = int(os.getenv('REDIS_DB', 0))
    
    # Si hay REDIS_URL, úsala directamente
    if redis_url:
        return {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [redis_url],
            },
        }
    
    # Configuración detallada para GCP o local
    redis_config = {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(redis_host, redis_port)],
        },
    }
    
    # Agregar password si está configurado
    if redis_password:
        redis_config['CONFIG']['hosts'] = [f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"]
    
    return redis_config

# Detectar si Redis está disponible
REDIS_AVAILABLE = True
try:
    import redis
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD')
    
    r = redis.Redis(
        host=redis_host, 
        port=redis_port, 
        password=redis_password,
        db=int(os.getenv('REDIS_DB', 0))
    )
    r.ping()
    
    # Configurar Channel Layers con Redis
    CHANNEL_LAYERS = {
        'default': get_redis_config()
    }
    
    if DEBUG:
        print(f"✅ Redis conectado exitosamente en {redis_host}:{redis_port}")
        
except Exception as e:
    REDIS_AVAILABLE = False
    
    # Usar backend en memoria para desarrollo
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
    
    if DEBUG:
        print("⚠️  Redis no está disponible. Usando InMemoryChannelLayer para WebSockets.")
        print(f"   Error: {str(e)}")
        print("   Para GCP: Configura REDIS_URL o REDIS_HOST en variables de entorno")
        print("   Para local: sudo apt install redis-server && sudo systemctl start redis-server")

# WebSocket settings
WEBSOCKET_ACCEPT_ALL = DEBUG  # Solo en desarrollo
WEBSOCKET_URL_PREFIX = '/ws/'

# Orders real-time settings
ORDERS_BROADCAST_GROUPS = {
    'business': 'orders_business_{business_id}',
    'kitchen': 'orders_kitchen_{business_id}',
    'waiters': 'orders_waiters_{business_id}',
    'managers': 'orders_managers_{business_id}',
}