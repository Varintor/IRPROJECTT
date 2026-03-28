import os

class Config:
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'postgresql://admin:admin@localhost:5432/recipe_app'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Elasticsearch configuration
    ELASTICSEARCH_URL = 'http://localhost:9200'
    ELASTICSEARCH_USER = 'elastic'
    ELASTICSEARCH_PASSWORD = '71WOZgaJD_=*y7kku*qe'
