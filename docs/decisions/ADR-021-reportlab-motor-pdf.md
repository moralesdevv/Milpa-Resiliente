# ADR-021: ReportLab como motor PDF soportado (WeasyPrint opcional)

- **Fecha:** 2026-11-16 · **Estado:** **propuesto** (cambia una tecnología declarada; ADR-011 la fijó con WeasyPrint)
- **Contexto:** WeasyPrint exige las bibliotecas nativas Pango/GObject. En Windows (host del equipo) no están, así que el PDF solo se generaba en la imagen Docker. El usuario fijó que la aplicación **debe funcionar sin Docker**.

## Decisión
1. `api.reports.pdf.render_pdf(ReportInput) -> bytes` genera el PDF con **ReportLab** (Python puro): A4, es / es+en, pie «Página X de Y», tablas con cabecera repetida, determinista (`invariant=1`).
2. `reportlab>=4.2,<5` pasa a dependencia de `apps/api`. `weasyprint` pasa al extra opcional `html-pdf`; la ruta HTML (`reports.renderer`) se conserva y sus pruebas se omiten con motivo si Pango no está.
3. Se mantiene el escaneo de privacidad previo: un informe `public` no puede llevar id/nombre de parcela, coordenadas precisas ni correos. Se corrigió un falso positivo real (un DOI se leía como coordenada y rechazaba todo informe público).
4. El PDF sigue registrando su SHA-256 (descarga verificable) y no cambia el contrato OpenAPI.

## Alternativas descartadas
- Exigir Docker/Pango: contradice la restricción del usuario.
- Generar el PDF en el navegador: pierde el hash servidor y la procedencia.

## Consecuencias / riesgos
- Dos rutas de render (ReportLab soportada; HTML/WeasyPrint opcional): la plantilla Jinja2 no es la fuente del PDF por defecto, y puede divergir. Se declara el PDF ReportLab como el oficial.
- Fuentes Vera incluidas en ReportLab: cobertura de caracteres limitada; los no soportados se sustituyen (`_clean`) en vez de fallar.
- **PostgreSQL 16 + PostGIS siguen siendo requisito** (no es el PDF).

**Módulos:** `reports/{pdf,contract,service,from_engine}.py`, `jobs/handlers/reports.py`, `cli.py report-sample`, `bench/runner.py`, `apps/api/pyproject.toml`.
**Relación:** reemplaza en lo operativo a ADR-011 (la política de recursos y privacidad de 011 sigue vigente para la ruta HTML). **Aprobadores:** R3, R4.
