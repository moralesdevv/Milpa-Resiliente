#!/bin/sh
# Arranque ordenado: migraciones (rol propietario) -> aplicación (rol sin BYPASSRLS).
# MIGRATION_DATABASE_URL se elimina del entorno antes de lanzar la API: el proceso de la aplicación
# NUNCA conserva credenciales de propietario.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
    echo "MIGRATION_DATABASE_URL es obligatoria cuando RUN_MIGRATIONS=true" >&2
    exit 1
  fi
  (cd /srv/milpa/apps/api && alembic upgrade head)
fi

# Paquete de demostración congelado (README §9): disponible sin red ni NASA. No sobrescribe.
if [ -d /opt/milpa/demo ] && [ ! -d "${DATA_DIR:-/data}/demo" ]; then
  cp -r /opt/milpa/demo "${DATA_DIR:-/data}/demo"
fi

unset MIGRATION_DATABASE_URL
exec "$@"
