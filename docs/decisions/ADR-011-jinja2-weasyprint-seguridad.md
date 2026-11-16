# ADR-011: Jinja2 + WeasyPrint y seguridad de renderizado

- **Fecha:** 2026-11-14 · **Estado:** aceptado

## Contexto
Los informes se generan con Jinja2 + WeasyPrint. WeasyPrint puede recuperar URL (http, file) → riesgo de SSRF y de lectura de archivos locales (README §22).

## Decisión
- Entrada validada (`ReportInput`, **PROVISIONAL_REPORT_INPUT_V0**: no es el `ReportModel` de R2; solo para la plantilla técnica provisional `report_provisional.html.j2`, rotulada en el propio PDF).
- Jinja2 `SandboxedEnvironment`, `autoescape`, `StrictUndefined`; los datos jamás se tratan como plantilla. El CSS de impresión propio se incrusta (marcado seguro) → el PDF no necesita recuperar nada.
- `url_fetcher` = `FetchGuard`: solo `data:`; deniega http/https/file/ftp/relativas, registra el intento (sin query string). `base_url=None`.
- Filtro de privacidad: un informe `public` se rechaza si su HTML contiene correos, coordenadas (>3 decimales) o JWT; los campos internos (nombre, código de parcela) solo se renderizan con `privacy_level=internal` y el contrato prohíbe combinarlos con `public`.
- Almacenamiento `reports/<report_id>.pdf` vía `ObjectStore`; SHA-256 calculado al escribir y **verificado en cada descarga** (500 `INTEGRITY_CHECK_FAILED` si no coincide).
- Fechas del PDF fijadas desde `generated_at` (`dcterms.created/modified`) → generación determinista.

## Alternativas
ReportLab (sin HTML/CSS reutilizable), Chromium headless (superficie enorme).

## Consecuencias / riesgos
Requiere Pango/HarfBuzz en la imagen (incluidos en `Dockerfile.app`); no carga en Windows nativo → las pruebas `pdf` corren en Docker. La plantilla final es de R4 y el modelo de R2: pendientes. **Aprobadores:** R3 (+R4 para plantilla final).
