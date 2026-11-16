#!/bin/sh
# Ejecuta la suite completa dentro de la imagen (Pango disponible) contra un PostGIS efímero.
# Sin dependencias externas: no descarga datos ni usa servicios de terceros.
set -eu
NET="milpa-test-net-$$"
DB="milpa-test-db-$$"
cleanup() { docker rm -f "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

docker build -f infra/Dockerfile.app --target test -t milpa-app:test .
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e POSTGRES_PASSWORD=postgres_test_only postgis/postgis:16-3.4 >/dev/null
i=0; until docker exec "$DB" pg_isready -U postgres >/dev/null 2>&1; do
  i=$((i+1)); [ "$i" -gt 60 ] && { echo "PostgreSQL no arrancó" >&2; exit 1; }; sleep 1
done
docker run --rm --network "$NET" \
  -e TEST_DATABASE_ADMIN_URL="postgresql+psycopg://postgres:postgres_test_only@$DB:5432/postgres" \
  milpa-app:test pytest -q -p no:cacheprovider "$@"
