# Contrato R3 → R4 (frontend)

## 1. Fuente de verdad
Las rutas usan las plantillas de la especificación (`{id}`, `{v}`, `{property}`, `{ip_id}`), que son las que indexa `openapi-fetch` (ADR-017).
`docs/openapi/openapi.json` (versionado; CI falla si difiere del generado: `make openapi`). Cada esquema declara `x-contract-status`:
- `confirmed_by_spec`: definido en la especificación.
- `provisional_r3`: propuesto por R3, **puede cambiar** (se avisará por ADR/RFC).
- `pending_r2`: DTO de R2 aún inexistente; llega como objeto opaco.

## 2. Servidor mock (sin motor)
`make mock` → `http://localhost:4010`. Responde solo ejemplos documentados con cabecera `X-Milpa-Mock: fixture` y `_mock: "fixture"`; los endpoints con DTO de R2 y las descargas PDF responden `501 MOCK_NO_EXAMPLE`. **No simula ciencia.**

## 3. Autenticación
`POST /v1/auth/login {email,password}` → `{access_token, token_type:"bearer", expires_at, expires_in, role}` (`expires_in` en segundos y `role` son aditivos para el cliente de R4; ADR-017). Enviar `Authorization: Bearer <jwt>`. Vida corta (15 min por defecto): al expirar la API responde `401 UNAUTHENTICATED` y el cliente debe volver a iniciar sesión (no hay *refresh*). No existe registro público. Roles: `tecnico`, `agricultor`, `admin`; `GET /v1/auth/me` devuelve el rol efectivo (el de la base de datos).

## 4. Errores (siempre `application/problem+json`)
`{type,title,status,code,detail,request_id,errors[{loc,msg,code}],hint?}`. Mostrar `request_id` al usuario en errores 5xx. Códigos y estados: ver `docs/API.md §4`. Los mensajes de validación **no repiten** lo enviado. `404` significa «no existe o no tiene acceso».

## 5. Trabajos asíncronos
Operaciones que devuelven `202 Accepted` + cabecera `Location: /v1/jobs/{id}` + cuerpo `JobOut`: crear zona, borrar parcela, corrida base, escenarios, informe. Sondear `GET /v1/jobs/{id}` hasta `ok|failed|cancelled`. Estados: `queued → running → ok|failed|cancelled`; `progress` ∈ [0,1] (puede ser `null`); `error = {code,type,message}` (por ejemplo `DEPENDENCY_NOT_INTEGRATED`); `result` versionado (`v`). `DELETE /v1/jobs/{id}` cancela (cooperativo si ya corre). Enviar `Idempotency-Key` (1-128 caracteres `[A-Za-z0-9._:-]`) para reintentos seguros: misma clave + misma operación = mismo trabajo; misma clave y otra operación = `409 IDEMPOTENCY_CONFLICT`.

## 6. Paginación, caché y límites
- Listas: `?limit=&cursor=` → `{items, next_cursor}`; `limit` máximo 100 (configurable). Cursor opaco; inválido → `400 INVALID_CURSOR`.
- `GET /v1/runs/{id}` y `/scenarios` devuelven `ETag`; reenviar `If-None-Match` → `304`.
- Límite de tasa por IP y usuario: `429 RATE_LIMITED` + `Retry-After`.
- CSV de suelo: `POST /v1/parcels/{id}/soil-samples` con `Content-Type: text/csv` (cuerpo = archivo, UTF-8, máx. 2 MiB por defecto → `413`); `?dry_run=true` valida sin guardar. Formato: el del README §9 (`parcel_code,sample_date,depth_from_cm,…`; contrato `SOIL_CSV_V1`); `parcel_code` debe ser el código de la parcela. Errores `422 CSV_VALIDATION_FAILED` con `errors[] = {loc:["csv", fila, columna], msg, code}` (todo o nada); la respuesta `200` trae conteos por propiedad, no filas (R4 espera `{accepted, errors}`: diferencia abierta C-05).

## 7. Informes
`POST /v1/reports` (trabajo) → cuando `ok`, `GET /v1/reports/{id}` da `pdf_url` y `sha256`; `GET /v1/reports/{id}/pdf` entrega `application/pdf` con `X-Content-SHA256` (la API verifica el hash en cada descarga; `500 INTEGRITY_CHECK_FAILED` si no coincide).

## 8. Plantilla del informe (R4 la entregó; falta el `report_model` de R2)
R4 entregó `report_es.html.j2`, `report_es_en.html.j2` y `report.css`. **Verificado** (auditoría 2026-11-15): renderizan en el sandbox de R3 con un contexto sintético construido desde `docs/REPORT_TEMPLATE.md` de R4 y producen un PDF A4 real (WeasyPrint 70, Docker); el `<link href="report.css">` se incrusta automáticamente (`render_template_pack`). **No integrada**: falta el adaptador `report_model` (R2) → contexto de la plantilla. Requisitos que se mantienen:
Archivos `apps/api/templates/report_es.html.j2` y `report_es_en.html.j2` + CSS de impresión, **sin recursos externos** (el PDF solo admite `data:`; el CSS se incrusta), con las variables del contrato de entrada (hoy `ReportInput`, provisional) o las del `ReportModel` de R2 cuando exista. Debe incluir: página principal, anexo técnico, `run_id`, `code_version`, hashes, referencias con versión de producto, supuestos, limitaciones, aviso «no es una recomendación automática»; los informes `public` **no** pueden contener nombre, código de parcela, correo ni coordenadas (la generación se aborta).

## 9. Diferencias abiertas con el borrador de R4 (`docs/auditoria/matriz_compatibilidad.md`)
`GET /healthz` (R4 dibujó `/v1/healthz`, C-06) · `DELETE /jobs/{id}` 200 vs 204 (C-03) · listados `Page[T]` vs arreglos (C-04) · forma de la carga de CSV (C-05) · `RunDTO`/`ParcelDTO`/`DataQualityDTO`/`ScenariosOut` (C-18) · ~40 DTO `pending_r2` (C-17). El cliente de R4 compila con 0 errores contra su borrador y con 302 contra este OpenAPI (comando en `docs/auditoria/informe_validacion.md`).

## 10. Entorno
CORS: configurar `CORS_ORIGINS` (lista; `*` prohibido). Estáticos: si existe `apps/web/dist` se sirven en `/`. Mapa: `MAP_TILE_URL`/`MAP_ATTRIBUTION` son configuración compartida (la API no las usa). Tipos TS: `make types` (`openapi-typescript`).

## 11. Privacidad que el frontend debe respetar
La ubicación de parcela se envía **una vez** al crear la parcela y se generaliza en el servidor (≥ 1 km); la API devuelve el centro de celda con 3 decimales. No almacenar ni registrar el punto original.
