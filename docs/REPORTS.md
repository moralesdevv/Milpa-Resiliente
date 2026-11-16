# Informes PDF (BE-07)

Flujo del servicio (`api.reports`): **validar** (`ReportInput`) → **renderizar** (Jinja2 sandbox + autoescape) → **filtro de privacidad** (informes `public`) → **PDF** (WeasyPrint, recursos restringidos) → **guardar** (`reports/<report_id>.pdf`, escritura atómica) → **SHA-256** → **registrar** (`report.report`) → **entregar verificando el hash** (`GET /v1/reports/{id}/pdf`).

## Estado de los insumos (no inventados)
| Pieza | Dueño | Estado |
|---|---|---|
| `ReportModel` (contenido científico) | R2 | pendiente → `ReportInput` es un **contrato de entrada provisional** (`PROVISIONAL_REPORT_INPUT_V0`) |
| Plantilla final bilingüe | R4 | pendiente → `apps/api/templates/report_provisional.html.j2` está **rotulada en el propio PDF** («PLANTILLA TÉCNICA PROVISIONAL … no es la plantilla final») |
| Generación a partir de una corrida real | R2+R4 | el trabajo `report` falla con `DEPENDENCY_NOT_INTEGRATED` (no genera contenido) |
No existe un endpoint que acepte contenido libre de informe: evita que un cliente inyecte un PDF «oficial».

## Contenido de la plantilla provisional
Página principal (zona, resumen es / es+en, secciones) · Anexo técnico (`run_id`, `code_version`, `region_config_hash`, `catalog_hash`, `data_hash`, `params_hash`, `seed`, secciones de anexo, procedencia/evidencia, supuestos, limitaciones, referencias con versión de producto) · aviso «no constituye una recomendación automática».

## Seguridad y privacidad
- `url_fetcher` = `FetchGuard`: solo `data:`; deniega y registra (sin query) http/https/file/ftp/rutas relativas; `base_url=None`; CSS incrustado ⇒ el PDF no necesita recuperar recursos (SSRF/lectura local bloqueados; prueba con HTML hostil).
- Jinja2: `SandboxedEnvironment`, `autoescape`, `StrictUndefined`; los datos no se interpretan como plantilla (`{{ 7*7 }}` se muestra literal).
- `privacy_level=public`: el contrato prohíbe campos internos (nombre, código de parcela) y el HTML se rechaza si contiene correo, coordenadas (>3 decimales) o JWT (`PublicReportPrivacyError`); no se escribe ningún archivo ni fila.
- Acceso: generador, o quien accede a la parcela de la corrida (RLS en `report.report`); informes `public` además requieren consentimiento `report_sharing` al solicitarlos.
- Determinismo: `dcterms.created/modified` se fijan desde `generated_at`; misma entrada ⇒ mismos bytes (misma imagen).

## Cómo generar un PDF de prueba
```bash
# Necesita Pango: dentro de la imagen
docker build -f infra/Dockerfile.app --target test -t milpa-app:test .
docker run --rm -v "$PWD/out:/out" milpa-app:test python -m api.cli report-sample --out /out/sample.pdf
# (imprime ruta, tamaño y sha256; datos sintéticos, plantilla provisional)
```
`make report` hace lo mismo en un host con Pango. En Windows nativo WeasyPrint no carga (falta `libgobject`): el error es explícito («ejecute dentro de la imagen Docker»).

## Pruebas
`apps/api/tests/test_reports.py` (contrato, plantilla, privacidad, SSRF, PDF, determinismo) y `tests/integration/test_reports_pdf.py` (BD real: hash registrado, descarga verificada, manipulación ⇒ 500, acceso por pertenencia). Las pruebas `pdf` requieren Pango: se omiten en el host y se ejecutan en `make test-docker`.

## Para integrar la plantilla de R4 y el modelo de R2
Añadir `ReportModel → ReportInput` (o sustituir el contrato por ADR), subir `TEMPLATE_VERSION`, mantener `FetchGuard`, el filtro público y las pruebas; actualizar `INTEGRATION_STATUS.md`.
