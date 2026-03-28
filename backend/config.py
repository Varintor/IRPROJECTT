import os

class Config:
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'postgresql://admin:admin@localhost:5432/recipe_app'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ FIX: Connection pool settings to prevent timeout
    SQLALCHEMY_POOL_SIZE = 10           # Base pool size
    SQLALCHEMY_MAX_OVERFLOW = 20        # Max overflow connections
    SQLALCHEMY_POOL_TIMEOUT = 30        # Connection timeout (seconds)
    SQLALCHEMY_POOL_RECYCLE = 3600      # Recycle connections after 1 hour
    SQLALCHEMY_POOL_PRE_PING = True     # Test connections before using
    SQLALCHEMY_ECHO = False             # Set to True to debug SQL queries

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Elasticsearch configuration
    ELASTICSEARCH_URL = 'http://localhost:9200'
    ELASTICSEARCH_USER = 'elastic'
    ELASTICSEARCH_PASSWORD = '71WOZgaJD_=*y7kku*qe'
