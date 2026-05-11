# Non-sensitive settings
from typing import List

# Required Environment Variables (app/config/.env file)
REQUIRED_ENV_VARS: List[str] = ['WEBEX_ADMIN_UID', 'CLIENT_ID', 'CLIENT_SECRET', 'SQLALCHEMY_DATABASE_URL', 'PUBLIC_URL']

# FastAPI Settings
APP_NAME: str = 'Webex Calling Monitor'
APP_VERSION: str = 'POC v1.0'
UVICORN_LOG_LEVEL: str = 'WARNING'

# Webex Integration URLs
AUTHORIZATION_BASE_URL = 'https://webexapis.com/v1/authorize'
TOKEN_URL = 'https://webexapis.com/v1/access_token'
WEBEX_BASE_URL = 'https://webexapis.com/v1/'
SCOPE: List[str] = ['spark:all', 'spark-admin:xsi', 'spark:xsi', 'spark-admin:locations_read', 'spark-admin:people_read', 'spark-admin:licenses_read', 'spark-admin:calls_write', 'spark:calls_write', 'spark:calls_read']

