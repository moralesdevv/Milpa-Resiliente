#!/bin/sh
# Crea el rol de la aplicación: NO superusuario, NO BYPASSRLS, NO propietario de tablas
# (spec R3 §9.4). Las migraciones las ejecuta POSTGRES_USER (propietario).
set -eu
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD es obligatoria}"
APP_ROLE="${APP_DB_ROLE:-milpa_app}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_role="$APP_ROLE" -v app_pw="$APP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE',
              :'app_role', :'app_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') \gexec
CREATE EXTENSION IF NOT EXISTS postgis;
SQL
