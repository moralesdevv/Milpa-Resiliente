#!/bin/sh
# Prueba de humo REAL de docker-compose.yml (db + app) con secretos efímeros generados aquí.
# Verifica arranque, migraciones, privilegios, integración de R1 (milpa-etl, catálogos, demo) y
# reproducción. Sale con código != 0 si alguna comprobación falla. Limpia todo al terminar.
#   sh infra/scripts/smoke-compose.sh     (también en Git Bash de Windows; no requiere MSYS_NO_PATHCONV)
set -u
cd "$(dirname "$0")/../.." || exit 1
PORT="${SMOKE_PORT:-18000}"
PROJECT="milpa-smoke-$$"
ENVF=".env.smoke-$$"   # relativo y cubierto por .gitignore (.env.*)
rnd() { head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
cat > "$ENVF" <<EOF
POSTGRES_DB=milpa
POSTGRES_USER=milpa_owner
POSTGRES_PASSWORD=$(rnd)
APP_DB_ROLE=milpa_app
APP_DB_PASSWORD=$(rnd)
JWT_SECRET=$(rnd)
MILPA_MODE=production
APP_PUBLISH=127.0.0.1:$PORT
EOF
C="docker compose --env-file $ENVF -p $PROJECT"
FAILS=0
cleanup() { $C down -v >/dev/null 2>&1; rm -f "$ENVF"; }
trap cleanup EXIT INT TERM
check() { # nombre esperado obtenido
  if [ "$2" = "$3" ]; then echo "OK    $1 ($3)"; else echo "FALLA $1: esperado '$2', obtenido '$3'"; FAILS=$((FAILS+1)); fi
}
sql() { $C exec -T db psql -U milpa_owner -d milpa -tAc "$1" 2>/dev/null | tr -d '\r'; }
app() { $C exec -T app "$@" 2>&1 | tr -d '\r'; }

echo "== build + up"
$C up -d --build >/dev/null 2>&1 || { echo "FALLA: docker compose up"; $C logs --no-color 2>&1 | tail -30; exit 1; }
code=000; i=0
while [ "$i" -lt 60 ]; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz" || true)
  [ "$code" = "200" ] && break
  i=$((i+1)); sleep 2
done
check "healthz" "200" "$code"
if [ "$code" != "200" ]; then $C logs --no-color 2>&1 | tail -40; exit 1; fi

check "rol de aplicación sin superusuario ni BYPASSRLS" "false|false" "$(sql "select rolsuper||'|'||rolbypassrls from pg_roles where rolname='milpa_app'")"
check "revisión Alembic" "0014" "$(sql "select version_num from alembic_version")"
check "semillas de R1: fuentes de datos" "3" "$(sql "select count(*) from prov.data_source")"
check "semillas de R1: propiedades de suelo" "8" "$(sql "select count(*) from ref.soil_property")"
check "vista de suelo con security_invoker" "t" "$(sql "select coalesce(reloptions @> array['security_invoker=true'], false) from pg_class where oid='soil.property_status'::regclass")"
check "uid del proceso" "10001" "$(app id -u)"
check "credenciales de propietario fuera del entorno de la API (PID 1)" "0" "$(app sh -c 'tr "\0" "\n" < /proc/1/environ | grep -c MIGRATION_DATABASE_URL || true')"
check "la base no publica puertos" "" "$($C port db 5432 2>/dev/null | head -1)"
check "sin token: 401" "401" "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/v1/zones")"

echo "== usuario por CLI y sesión"
PW="clave-de-humo-$(rnd | cut -c1-12)"
$C exec -T -e NEW_USER_PASSWORD="$PW" app python -m api.cli create-user --email humo@example.org --role tecnico >/dev/null 2>&1
LOGIN=$(curl -s -X POST "http://127.0.0.1:$PORT/v1/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"humo@example.org\",\"password\":\"$PW\"}")
TOK=$(printf '%s' "$LOGIN" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
check "login devuelve rol y vigencia" "tecnico|900" "$(printf '%s' "$LOGIN" | sed -n 's/.*"expires_in":\([0-9]*\).*"role":"\([a-z]*\)".*/\2|\1/p')"
check "con token: 200" "200" "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOK" "http://127.0.0.1:$PORT/v1/zones")"
check "catálogo de propiedades visible para la API" "200" "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOK" "http://127.0.0.1:$PORT/v1/catalog/crops")"

echo "== R1 dentro de la imagen"
check "milpa-etl instalado (catálogo sandbox válido)" "0" "$(app sh -c 'cd /srv/milpa && python -m milpa_etl.cli check-catalog catalogs/crops.yaml --mode sandbox >/dev/null 2>&1; echo $?')"
check "catálogo en producción se rechaza (pending, P9)" "2" "$(app sh -c 'cd /srv/milpa && python -m milpa_etl.cli check-catalog catalogs/crops.yaml --mode production >/dev/null 2>&1; echo $?')"
check "demo congelado sembrado en DATA_DIR" "datos sintéticos" "$(app sh -c 'sed -n "s/.*\"label\": \"\([^\"]*\)\".*/\1/p" /data/demo/EXPECTED.json')"
REPRO=$(app sh -c 'python -m api.cli reproduce --data-dir /data; echo "exit=$?"')
check "reproduce: capa de datos verificada" "5" "$(printf '%s\n' "$REPRO" | grep -c '^VERIFICADO')"
check "reproduce: no declara éxito sin R2" "exit=3" "$(printf '%s\n' "$REPRO" | grep '^exit=')"
check "análisis sin R2: 404/503, nunca datos simulados" "404" "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOK" "http://127.0.0.1:$PORT/v1/runs/00000000-0000-4000-8000-000000000000/summary?scenario=BASE")"

echo "== PDF y registros"
check "PDF de muestra en la imagen" "0" "$(app sh -c 'python -m api.cli report-sample --out /data/results/smoke.pdf >/dev/null 2>&1; echo $?')"
check "sin correos, claves ni tokens en los registros" "0" "$($C logs --no-color app 2>&1 | grep -cE "humo@example|$PW|eyJ" || true)"

echo "== reinicio"
$C restart app >/dev/null 2>&1
code=000; i=0
while [ "$i" -lt 40 ]; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/healthz" || true)
  [ "$code" = "200" ] && break
  i=$((i+1)); sleep 2
done
check "healthz tras reinicio" "200" "$code"
check "login persiste tras reinicio" "200" "$(curl -s -o /dev/null -w '%{http_code}' -X POST "http://127.0.0.1:$PORT/v1/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"humo@example.org\",\"password\":\"$PW\"}")"

echo
if [ "$FAILS" -eq 0 ]; then echo "HUMO: todas las comprobaciones OK"; else echo "HUMO: $FAILS comprobación(es) FALLARON"; fi
exit "$FAILS"
