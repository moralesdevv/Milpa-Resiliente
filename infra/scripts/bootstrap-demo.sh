#!/bin/sh
# Prepara una base NUEVA para la demo pública: registra manifiesto, zona piloto, procedencia y DEM con la
# ETL de R1. Es IDEMPOTENTE (se puede ejecutar en cada arranque). Requiere el rol PROPIETARIO
# (MIGRATION_DATABASE_URL): la API nunca conserva esas credenciales (entrypoint.sh).
#
# Datos que usa (ya curados con datos REALES de NASA POWER / GPM IMERG; no se descarga nada aquí):
#   $DATA_DIR/curated/camotan_jocotan  $DATA_DIR/manifest  $DATA_DIR/raw  $DATA_DIR/dem/*.tif
# Si faltan, el paso se omite con un aviso y la API los reporta como «no disponibles» (nunca inventa).
set -u
ZONE="${DEMO_ZONE:-camotan_jocotan}"
DATA="${DATA_DIR:-/data}"
SEED="${SEED_DIR:-/opt/milpa/seed}"
cd "${APP_ROOT:-/srv/milpa}" || exit 1

# --- datos semilla: copia no destructiva hacia DATA_DIR ---------------------------------------
if [ -d "$SEED" ]; then
  for d in curated manifest raw dem; do
    [ -d "$SEED/$d" ] && mkdir -p "$DATA/$d" && cp -rn "$SEED/$d/." "$DATA/$d/" 2>/dev/null
  done
fi

if [ -z "${MIGRATION_DATABASE_URL:-}" ]; then
  echo "bootstrap-demo: falta MIGRATION_DATABASE_URL (rol propietario); se omite" >&2
  exit 0
fi
# La ETL usa psycopg directo: sin el sufijo del dialecto de SQLAlchemy.
DATABASE_URL=$(printf '%s' "$MIGRATION_DATABASE_URL" | sed 's#^postgresql+psycopg://#postgresql://#')
export DATABASE_URL DATA_DIR="$DATA"
ETL="python -m milpa_etl.cli"

if [ ! -f "$DATA/curated/$ZONE/daily.parquet" ]; then
  echo "bootstrap-demo: no hay serie curada de $ZONE en $DATA/curated; la zona no se registra" >&2
  exit 0
fi
GEOJSON="regions/$ZONE.geojson"
[ -f "$GEOJSON" ] || { echo "bootstrap-demo: falta $GEOJSON" >&2; exit 0; }

$ETL register manifest || echo "bootstrap-demo: AVISO register manifest falló" >&2
$ETL register zone --zone "$ZONE" --geojson "$GEOJSON" --region-config regions/pilot_corredor_seco.yaml \
  || { echo "bootstrap-demo: AVISO register zone falló" >&2; exit 0; }
$ETL register provenance --zone "$ZONE" || echo "bootstrap-demo: AVISO register provenance falló" >&2

TIF=$(ls "$DATA"/dem/*.tif 2>/dev/null | head -1)
if [ -n "$TIF" ]; then
  $ETL fetch dem --zone "$ZONE" --geojson "$GEOJSON" --tif "$TIF" \
    || echo "bootstrap-demo: AVISO el DEM no se registró (¿rasterio instalado?); elevación/pendiente quedan «no disponibles»" >&2
else
  echo "bootstrap-demo: sin DEM local; elevación/pendiente quedan «no disponibles»" >&2
fi
echo "bootstrap-demo: zona $ZONE lista"
