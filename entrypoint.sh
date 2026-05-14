#!/bin/sh
set -e

# Write env vars to app/config/.env because the app reads via dotenv_values()
mkdir -p /app/app/config
cat > /app/app/config/.env <<EOF
WEBEX_ADMIN_UID=${WEBEX_ADMIN_UID}
CLIENT_ID=${CLIENT_ID}
CLIENT_SECRET=${CLIENT_SECRET}
SQLALCHEMY_DATABASE_URL=${SQLALCHEMY_DATABASE_URL}
PUBLIC_URL=${PUBLIC_URL}
EOF

exec "$@"
