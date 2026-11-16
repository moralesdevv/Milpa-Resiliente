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
  # Catálogo y grilla de escenarios de R2 (idempotente; rol propietario)
  (cd /srv/milpa && python -m api.cli register-engine)
  # Cuenta de la sesión pública de demostración (sin contraseña utilizable), solo si está habilitada
  if [ "${DEMO_PUBLIC_ACCESS:-false}" = "true" ]; then
    (cd /srv/milpa && python -m api.cli create-demo-user)
  fi
  # Zona piloto + datos curados reales para la demo pública (idempotente; ver infra/scripts/bootstrap-demo.sh)
  if [ "${BOOTSTRAP_DEMO:-${DEMO_PUBLIC_ACCESS:-false}}" = "true" ]; then
    sh /usr/local/bin/bootstrap-demo.sh || echo "entrypoint: bootstrap-demo terminó con error (se continúa)" >&2
  fi
fi

# Paquete de demostración congelado (README §9): disponible sin red ni NASA. No sobrescribe.
if [ -d /opt/milpa/demo ] && [ ! -d "${DATA_DIR:-/data}/demo" ]; then
  cp -r /opt/milpa/demo "${DATA_DIR:-/data}/demo"
fi

unset MIGRATION_DATABASE_URL
exec "$@"
