# Base de datos (PostgreSQL 16 + PostGIS 3.4)

> **Actualización 2026-11-16:** la última migración es la **0014** (semillas de R1). Las tablas `engine.analysis_run`, `engine.scenario_run` y `ref.catalog_release` se escriben ahora con el motor real (trabajos de la API); `engine.scenario_def` se siembra con `python -m api.cli register-engine` (rol propietario). `engine.risk_summary`/`planting_summary` aún no se llenan (las lecturas salen del motor).

Cadena Alembic **única**: `apps/api/migrations` (ADR-003). DDL en `migrations/sql/NNNN_*.up.sql`; cada revisión Python lo ejecuta y define su `downgrade`.

| Rev. | Contenido | Propietario del contenido |
|---|---|---|
| 0001 `base` | extensión PostGIS, 10 esquemas, 17 tipos enumerados | R3 |
| 0002 `auth` | `app_user`, `consent`, `audit_log` | R3 |
| 0003 `prov` | `citation, data_source, ingestion_run, indicator_provenance` | **R1 (provisional)** |
| 0004 `ref` | `soil_property, catalog_release, crop…, strategy…` (FK a `geo.region` diferida, C3) | **R1 (provisional)** |
| 0005 `geo` | `region, zone, climate_cell, zone_cell` + FK diferida | **R1 (provisional)** |
| 0006 `farm` | `farmer, parcel, parcel_history, priority_profile, technician_assignment` | R3 |
| 0007 `private` | `parcel_geometry` (nivel B, desactivada) | R3 |
| 0008 `soil` | `sample, measurement, declaration, estimate`, vista `property_status` | **R1 (provisional)** |
| 0009 `econ` | `price_record, cost_record` | **R1 (provisional)** |
| 0010 `engine` | `analysis_run, scenario_def, scenario_run, risk_summary, planting_summary, ranking_result, ranking_stability, soil_voi_result, job` | `job`: R3; resto: estructura README, semántica R2 |
| 0011 `report` | `report` | R3 |
| 0012 `rls` | funciones de autorización + políticas RLS | R3 |
| 0013 `grants` | privilegios mínimos del rol de aplicación | R3 |

Verificado: migración desde base vacía, `downgrade base` y re-`upgrade` (`test_migrations.py`).

## Extensiones de R3 sobre el DDL del README (marcadas `R3-EXT` en el SQL)
`auth.app_user`: `created_at, failed_login_count, last_failed_login_at, locked_until` · `auth.consent`: índice único vigente por (sujeto, propósito) · `auth.audit_log` (nueva) · `farm.farmer`: `created_at`, único por usuario · `farm.parcel`: `created_at, created_by` · `farm.priority_profile`: `updated_at`, único por parcela · `engine.job.kind` admite `parcel_delete` y `consent_purge` (ADR-007) · `engine.job.progress` ∈ [0,1].

## Roles
| Rol | Atributos | Uso |
|---|---|---|
| propietario (`POSTGRES_USER`) | dueño de objetos | migraciones, CLI de alta de usuarios |
| `milpa_app` (`APP_DB_ROLE`) | `NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`, **no propietario** | la API y los workers |
`0013_grants` aborta si el rol no existe, es superusuario o tiene `BYPASSRLS`. Privilegios por tabla/columna (p. ej. `UPDATE` solo de `failed_login_count, last_failed_login_at, locked_until` en `app_user`; `INSERT, SELECT` en `audit_log`; R1 solo lectura salvo `geo.zone` INSERT/UPDATE y `prov.indicator_provenance` INSERT/DELETE).

## RLS
Tablas con RLS: `farm.farmer, parcel, parcel_history, priority_profile, technician_assignment`, `private.parcel_geometry`, `soil.sample, measurement, declaration`, `report.report` (`soil.estimate` es zonal y público). Contexto: `SET LOCAL app.user_id` por transacción (`auth.current_user_id()`).
- Visibilidad de lectura: `farm.visible_farmers()` / `farm.visible_parcels()` (SECURITY DEFINER, evaluadas **una vez por consulta**; medido: `count(*)` con RLS 4 840 ms → 23 ms sobre 10 000 filas).
- Dueño: `farm.is_farmer_owner` / `is_parcel_owner` (borrado, geometría privada, asignaciones).
- Técnico: asignación no revocada **y** consentimiento `analysis` del agricultor no retirado.
- Procedencia: `prov.can_access_ip(ip_id)` — un indicador ligado a medición/declaración/historial/corrida de una parcela solo es visible con acceso a esa parcela.
- `soil.property_status` usa `security_invoker=true`.

## Operación
```bash
# Fuera de Docker (requiere PostgreSQL+PostGIS y los dos roles; ver .env.example)
cd apps/api && uv run alembic upgrade head      # = make db-migrate
uv run alembic downgrade base                   # solo desarrollo
uv run alembic current
```
Alembic lee `MIGRATION_DATABASE_URL` (propietario) y `APP_DB_ROLE` (por defecto `milpa_app`); no hay URL ni credenciales en `alembic.ini`.
