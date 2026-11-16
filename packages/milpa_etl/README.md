# milpa_etl — R1 · Datos y evidencia (integrado en el repositorio raíz)

Código y datos de R1 traídos de `references/Milpa-Resiliente-R1` (que se conserva intacto como referencia).
Pipeline de datos del MVP: ingesta de clima (NASA POWER, IMERG), curación, ET0 y precipitación efectiva
por decena, y registro de procedencia y nivel de evidencia (A/B/C) en PostgreSQL.

> Principio rector de R1: **sin cita no hay umbral.** Todo parámetro agronómico sigue en `pending`
> (`catalogs/crops.yaml`, `regions/pilot_corredor_seco.yaml`). Nada se inventa.

## Qué cambió respecto de la entrega original (solo mecánica; el comportamiento es el de R1)
| Original | Aquí |
|---|---|
| Scripts sueltos (`milpa_r1.py`, `imerg_r1.py`, `registrar_*.py`…) | Paquete `milpa_etl` (`core`, `imerg`, `quality`, `loaders/*`, `diagnostics/*`) y CLI única `milpa-etl` |
| `seed_catalogo.py` y `fetch_dem.py` usaban `psycopg2` aunque `requirements.txt` pedía `psycopg` 3 | Portados a `psycopg` 3 (adaptadores NumPy incluidos) |
| `sql/*.sql` (DDL + semillas) | El DDL es **una sola cadena Alembic** (`apps/api/migrations`, ADR-003); las semillas 90/91/93 son la revisión `0014`. **`92_soil_fixture_provenance.sql` no se aplica** (quita `security_invoker` y evade RLS) |
| `catalogs/`, `regions/`, `data/curated/` | `catalogs/`, `regions/` y `data/curated/` en la raíz (README §23); `data/demo/` generado con `milpa-etl build-demo` |
| CLI con `argparse` (README §9 menciona Typer) | Se conserva `argparse`: sin dependencia nueva ni reescritura de código verificado |

## CLI
```
milpa-etl fetch power|imerg|dem ...        milpa-etl curate|validate --zone Z --lat .. --elev ..
milpa-etl merge imerg --zone Z             milpa-etl ingest soil-csv --parcel P-014 --file suelo.csv
milpa-etl build-demo | selftest | scan-privacy | check-catalog FILE [--mode production]
milpa-etl seed catalog --catalog catalogs/crops.yaml            # escribe ref.* (rol propietario)
milpa-etl register zone|manifest|provenance ...                 # escriben prov/geo (rol propietario)
```
Variables: `DATA_DIR` (por defecto `data`), `DATABASE_URL` (**rol propietario**, solo para `seed`/`register`/`fetch dem`),
`EARTHDATA_TOKEN` (IMERG; autorizar GES DISC en Earthdata), `MILPA_MODE` (`sandbox`|`production`).

## Orden para una zona nueva (requiere red; ver `make data`, `make register`)
```
fetch power → [fetch imerg por año → merge imerg] → curate → validate        # archivos bajo data/curated/<zona>/
register manifest → register zone → register provenance                       # BD (propietario)
```
`register provenance` exige las ingestas en `prov.ingestion_run` (`register manifest`), que salen de
`data/manifest/ingestions.jsonl`: ese manifiesto y los JSON crudos **no vienen en el repositorio** (se generan al
descargar). No se reconstruye linaje que no existe.

## Verificar
```
make test-etl           # CLI, catálogos pending, demo sin datos personales, cargador de suelo de R1
milpa-etl selftest      # 24 pruebas propias de R1 (ET0 FAO-56 ejemplo 18, Pef, relleno de huecos, determinismo…)
make reproduce          # verifica data/demo (hashes) y regenera el data_hash con esta ETL; sale 3 sin R2
```

## Límites conocidos de R1 (no resueltos aquí)
Lluvia evidencia C (IMERG sin validación local; 81 % de los días son POWER), sin corrección de sesgo;
convención de día UTC vs UTC−6 sin resolver; ET0 y Pef se calculan aquí aunque el README los asigna al motor (R2);
parámetros agronómicos `pending`. Detalle y cifras en `docs/auditoria/`.
