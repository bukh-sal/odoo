#!/bin/sh
set -eu
export MP_APP_PASSWORD="$(cat /run/secrets/app_db_password)"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\getenv app_password MP_APP_PASSWORD
CREATE ROLE modular LOGIN CREATEDB NOSUPERUSER NOCREATEROLE PASSWORD :'app_password';
SQL
unset MP_APP_PASSWORD
