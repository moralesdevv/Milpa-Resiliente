# API (R3) — rutas, autenticación, errores y ejemplos

> **Actualización 2026-11-16:** nuevo `POST /v1/auth/demo-session` (ADR-019). `heatmap` y `dekad-chart` aceptan `strategy`/`variety` por código y `dekad-chart` filtra por `cohort_year`, `cycle`, `plant_date`. `climate-history` devuelve totales anuales de lluvia observada y ET0 del motor. `POST /v1/reports` genera el informe desde el modelo del motor (sin PDF si no hay Pango).

OpenAPI: `docs/openapi/openapi.json` (regenerar con `make openapi`) · interactivo en `/docs` y `/openapi.json` con la app en marcha. Prefijo `/v1`. Este documento solo afirma lo implementado; los contratos no definidos por la especificación se marcan **provisional**.

## 1. Convenciones
- `Authorization: Bearer <JWT>` (ver `docs/SECURITY.md`). Excepciones públicas: `POST /v1/auth/login`, `GET /healthz`.
- Errores: `application/problem+json` con `{type,title,status,code,detail,request_id,errors,hint?}`; `X-Request-ID` en toda respuesta.
- Listas: `Page[T] = {items,next_cursor}`, `limit` ≤ 100.
- Trabajos: `202` + `Location: /v1/jobs/{id}`; `Idempotency-Key` opcional.
- Caché: `ETag` en `/runs/{id}` y `/runs/{id}/scenarios`.
- Modo demo (`DEMO_READONLY=true`): toda escritura salvo login → `403 READ_ONLY_MODE`.

## 2. Endpoints (36 operaciones; incluye extensiones provisionales de validación agrícola)
**Estado:** *impl* = implementado y probado con PostgreSQL real; *R2/R1* = el adaptador responde 503 hasta que el componente exista.

| Método y ruta | Roles | Modo | Estado / notas |
|---|---|---|---|
| `POST /auth/login` | público | sync | impl · bloqueo progresivo · respuesta `{access_token, token_type, expires_at, expires_in, role}` |
| `GET /auth/me` | autenticado | sync | impl |
| `GET /zones`, `GET /zones/{id}` | autenticado | sync | impl (geometría de zona = dato público) |
| `POST /zones` | tecnico, admin | **202** | impl (zona + trabajo `zone_ingest`; la ingesta es R1 → el trabajo termina `failed: DEPENDENCY_NOT_INTEGRATED`). Cuerpo **provisional** |
| `GET /zones/{id}/data-quality` | autenticado | sync | impl sobre `coverage.parquet` (503 `DATASET_UNAVAILABLE/INCOMPATIBLE`); sesgos IMERG/POWER = `pending_r1` |
| `POST /parcels/{id}/planting-validation` | dueño o técnico asignado | sync | sandbox; reglas configurables + serie zonal histórica POWER/IMERG; no es pronóstico ni validación parcelaria |
| `GET /zones/{id}/planting-validation` | autenticado, incluye demo | sync | sandbox; mismo cálculo agregado por zona; fecha y variedad en query |
| `POST /parcels` | agricultor, tecnico | sync 201 | impl · generaliza la ubicación ≥1 km · exige consentimiento `analysis` · cuerpo **provisional** |
| `GET /parcels/{id}` | dueño o técnico asignado | sync | impl (404 si no visible) |
| `DELETE /parcels/{id}` | dueño | **202** | impl (trabajo `parcel_delete`; vía admin bloqueada, ADR-015) |
| `GET /parcels/{id}/soil` | dueño / técnico asignado | sync | impl (`value` = valor + `ip_id`, **no** el `Indicator` de R2) |
| `POST /parcels/{id}/soil-samples` | dueño / técnico asignado | sync | impl · `text/csv` · `dry_run` · guardar exige `EvidencePort` (R2) |
| `PUT /parcels/{id}/soil-declarations/{property}` | dueño / técnico asignado | sync | impl · guardar exige `EvidencePort` (R2) |
| `PUT /parcels/{id}/priority-profile` | dueño / técnico asignado | sync | impl |
| `GET /catalog/crops|strategies|references`, `GET /catalog/strategies/{id}/versions/{v}` | autenticado | sync | impl (lectura de `ref.*`; `Page[T]` con `limit/cursor`; vacío sin datos de R1) |
| `POST /zones/{id}/runs` | tecnico, admin | **202** | impl (trabajo `analysis_run`; ejecución = R2) |
| `GET /runs/{id}` | acceso a la corrida | sync | impl (estado, modo, razones, hashes) |
| `GET /runs/{id}/scenarios` | acceso | sync | impl |
| `POST /runs/{id}/scenarios` | tecnico, admin | **202** | impl (trabajo `scenario_run`; ejecución = R2) |
| `GET /runs/{id}/climate-history|summary|heatmap|dekad-chart` | acceso | sync | **R2**: 503 `DEPENDENCY_NOT_INTEGRATED`; 409 `SCENARIO_NOT_COMPUTED`/`RUN_NOT_READY` ya implementados |
| `POST /runs/{id}/rank` | acceso | sync | **R2** (validación `RankRequest` impl) |
| `POST /runs/{id}/soil-voi` | dueño / técnico asignado | sync | **R2** |
| `GET /provenance/{ip_id}` | acceso al recurso dueño del indicador | sync | impl · forma `ProvenanceInfo` (README §15) + `ip_id`, `indicator_code`, `unit` |
| `POST /reports` | tecnico o dueño (+consentimientos) | **202** | impl (trabajo `report`; contenido = R2/R4) |
| `GET /reports/{id}`, `GET /reports/{id}/pdf` | generador o acceso a la parcela | sync | impl (verifica SHA-256 al descargar) |
| `GET /jobs/{id}`, `DELETE /jobs/{id}` | creador o admin | sync | impl |
| `GET /healthz` | público | sync | impl (`{status,db}`) |

Sin endpoint (contrato no definido, ADR-010): registro de usuarios, consentimiento, asignación de técnicos → servicios + CLI (`python -m api.cli`).

## 3. Autenticación
```bash
curl -s -X POST http://localhost:8000/v1/auth/login -H 'Content-Type: application/json' \
     -d '{"email":"tecnico@example.org","password":"<contraseña>"}'
# {"access_token":"<jwt>","token_type":"bearer","expires_at":"2026-11-15T12:15:00Z"}
curl -s http://localhost:8000/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

## 4. Códigos de error
**Especificación:** `MIXED_CYCLE_LENGTH, MULTIPLE_SWEEP_CYCLES, MISSING_THRESHOLD_CITATION, INSUFFICIENT_SOIL_DATA, NOT_COMPARABLE, RUN_NOT_READY (409), SCENARIO_NOT_COMPUTED (409), CSV_VALIDATION_FAILED (422), VALIDATION_ERROR (400/422), UNAUTHENTICATED (401), FORBIDDEN (403), NOT_FOUND (404), RATE_LIMITED (429)`.
**Extensión R3 (pendiente de aprobación, ADR-010):** `DEPENDENCY_NOT_INTEGRATED (503), DATASET_UNAVAILABLE (503), DATASET_INCOMPATIBLE (503), INTEGRITY_CHECK_FAILED (500), IDEMPOTENCY_CONFLICT (409), PAYLOAD_TOO_LARGE (413), UNSUPPORTED_MEDIA_TYPE (415), CONSENT_REQUIRED (403), READ_ONLY_MODE (403), INVALID_CURSOR (400), SERVICE_UNAVAILABLE (503), INTERNAL_ERROR (500)`.
`MULTIPLE_SWEEP_CYCLES` está declarado pero ningún camino de R3 lo produce (depende de R2).

## 5. Ejemplos
```bash
# Crear parcela (la ubicación se generaliza en el servidor; el punto no se guarda)
curl -s -X POST :8000/v1/parcels -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"zone_id":"<uuid>","code":"P-1","area_ha":"1.50","location":{"lat":14.5,"lon":-89.5}}'

# Validar un CSV de suelo sin guardar (formato del README §9; parcel_code = código de la parcela)
#   parcel_code,sample_date,depth_from_cm,depth_to_cm,lab,ph,ph_method,om_pct,om_method,sand_pct,silt_pct,clay_pct,texture_method,cec_cmol_kg,cec_method,effective_root_depth_cm,awc_mm_per_m,awc_method
curl -s -X POST ':8000/v1/parcels/<id>/soil-samples?dry_run=true' -H "Authorization: Bearer $T" \
  -H 'Content-Type: text/csv' --data-binary @suelo.csv

# Borrado definitivo (trabajo) y seguimiento
curl -si -X DELETE :8000/v1/parcels/<id> -H "Authorization: Bearer $T" -H 'Idempotency-Key: borrar-p1'
curl -s :8000/v1/jobs/<job_id> -H "Authorization: Bearer $T"
```

## Plantillas de ruta
Las rutas con parámetro usan las plantillas de la especificación (`{id}`, `{v}`, `{property}`, `{ip_id}`) para que los clientes tipados (`openapi-fetch`) coincidan; en el código los parámetros conservan nombres descriptivos (alias de `Path`). Ver ADR-017.
