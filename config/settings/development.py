from config.settings.base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

CORS_ALLOW_ALL_ORIGINS = True

# We can override database here if needed, but base uses SQLite by default, which is perfect for dev.
