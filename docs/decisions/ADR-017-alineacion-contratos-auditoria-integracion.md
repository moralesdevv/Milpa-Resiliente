# ADR-017: Alineación de contratos con la especificación y defensas de integración (auditoría 2026-11-15)

- **Fecha:** 2026-11-15 · **Estado:** **propuesto** (cambia contratos compartidos con R1/R4; requiere su confirmación)
- **Relación:** corrige decisiones previas de ADR-003 (migraciones), ADR-009/010 (contratos provisionales) y ADR-011 (renderizado).

## Contexto / problema
Al recibir los entregables reales de R1 y R4 (`references/`) se compararon con R3 de forma ejecutable (`docs/auditoria/`). Aparecieron desvíos **de R3** respecto de la especificación y un riesgo de seguridad introducido por un script de R1.

## Decisión
1. **Guardia de arranque de seguridad (`api.db.invariants`).** El servicio se niega a arrancar si el rol de la aplicación es superusuario o tiene BYPASSRLS, si falta RLS en una tabla protegida o si una vista de los esquemas de datos no usa `security_invoker`. *Motivo:* `sql/92_soil_fixture_provenance.sql` de R1 elimina `security_invoker` de `soil.property_status` y, medido, un usuario sin parcelas ve filas de parcelas ajenas. Falla cerrado; si la BD no responde, solo se registra (el `/healthz` lo refleja).
2. **CSV de suelo `SOIL_CSV_V1`** = el formato que fija el README §9 (y que R1 ejemplifica). Sustituye al contrato `SOIL_CSV_V0_PROVISIONAL` que R3 había inventado. Decisiones de R3 donde el texto calla: `parcel_code` debe coincidir con el código de la parcela destino (la representatividad `parcela` se deriva de eso); `effective_root_depth_cm` usa el método `declarado/medido` del catálogo; textura completa si hay alguna componente; se rechazan celdas de texto libre que empiecen por `= + - @` (inyección de fórmulas).
3. **`ProvenanceOut` adopta los nombres de `ProvenanceInfo`** (README §15): `evidence`, `evidence_rule`, `method`, `period{start,end}`, `spatial_res`, `temporal_res`, `sources[]`. Se conservan `ip_id`, `indicator_code`, `unit` (aditivos). `Period` y el formato de `spatial_res`/`temporal_res` no están definidos en la especificación: forma propuesta (`"10000 m"`, ISO 8601 `"P1D"`).
4. **Plantillas de ruta como la especificación** (`{id}`, `{v}`, `{property}`, `{ip_id}`) mediante alias de `Path`. La URL en ejecución no cambia; sí cambia el OpenAPI (clientes tipados indexan por plantilla).
5. **Login**: `TokenResponse` añade `expires_in` (segundos) y `role` (aditivos; se conservan `expires_at`, `token_type`). Ninguna especificación define este DTO.
6. **PDF**: `GET /reports/{id}/pdf` documenta solo `application/pdf`.
7. **Renderizado de plantillas de paquete** (`render_template_pack`, `inline_local_stylesheets`): se incrustan las hojas de estilo locales de la carpeta de plantillas (nombre simple, archivo regular, sin `url()`/`@import`/`</`). La política de red del PDF sigue siendo «solo `data:`».

## Alternativas descartadas
- *Permitir lectura de archivos locales en el `url_fetcher`* para el CSS: amplía la superficie SSRF/lectura de archivos.
- *Parchear el SQL de R1 o ejecutarlo en la base*: la cadena Alembic de R3 es la única fuente de DDL (ADR-003).
- *Mantener nombres de columna en `ProvenanceOut`*: contradice §15 y rompe a R4.
- *Reintroducir el contrato CSV propio como alternativa*: duplica contratos.

## Consecuencias
- R1 debe corregir su script 92 (hasta entonces, **no ejecutarlo**: el servicio no arrancará).
- Clientes que usaban `evidence_level`/`evidence_rule_id`/`processing_method`/`period_start`/`period_end`/`spatial_res_m` de `/provenance` deben migrar (no hay consumidores externos conocidos; R4 usa los de §15).
- Los CSV con el formato antiguo de R3 (`sampled_at`, `representativeness`) se rechazan con `unknown_column`.

## Riesgos
- `Period`, `spatial_res`, `temporal_res`, `expires_in`, `role` son formas **propuestas** por R3 (`x-contract-status: provisional_r3`); R2/R4 pueden pedir otra.
- La guardia no detecta todas las formas de evadir RLS (p. ej. funciones `SECURITY DEFINER` nuevas); cubre las tres identificadas.

## Módulos afectados
`api/db/invariants.py`, `api/main.py`, `api/soil_csv.py`, `api/services/{parcels,runs,auth}.py`, `api/schemas/{runs,auth,parcels}.py`, `api/routers/*`, `api/reports/renderer.py`, `docs/openapi/openapi.json`.

## Pruebas
`tests/contract/test_r1_artifacts.py`, `tests/contract/test_r4_artifacts.py`, `tests/integration/test_hardening.py`, `test_api_auth.py`, `test_api_analysis.py`, `apps/api/tests/test_storage_hashing_csv.py`.

**Aprobadores:** R3 (técnico), R1 y R4 (contratos que consumen), R2 (`Indicator`/DTO).
