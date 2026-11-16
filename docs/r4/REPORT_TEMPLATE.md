# Plantilla de informe R4 para integración con R3

Estado: **plantilla HTML/Jinja2 entregada**, no verificada con WeasyPrint ni con el `report_model` real de R2. R4 no genera un PDF paralelo ni recalcula resultados: R3 carga estas plantillas, las llena con `report_model` y renderiza el PDF.

## Archivos (ubicación del §23)

| Archivo | Contenido |
|---|---|
| `apps/api/templates/report_es.html.j2` | Página principal A4 + anexo técnico, en español |
| `apps/api/templates/report_es_en.html.j2` | Extiende la anterior y añade el resumen ejecutivo en inglés (`locale = es+en`) |
| `apps/api/templates/report.css` | Estilos de impresión; sin fuentes ni imágenes externas (compatible con un `url_fetcher` local, §22) |

Se comprobó únicamente que ambas plantillas renderizan con Jinja2 (`autoescape=True`, `StrictUndefined`) con un contexto de ejemplo y que la variante `es` omite el resumen en inglés. **No** se ha renderizado el PDF.

## Contrato de variables que consume la plantilla

R3/R2 deben proveerlas desde `report_model`; la plantilla no inventa ninguna.

| Variable | Contenido |
|---|---|
| `labels` | Diccionario de textos fijos por idioma (incluye `not_automatic`, `not_automatic_en`, `privacy_names`). Los textos del glosario salen de la misma fuente que la interfaz |
| `report` | `run_id`, `privacy_level` (`internal`/`public`), `code_version`, `region_config_hash`, `catalog_hash`, `data_hash`, `params_hash`, `seed` |
| `mode` | `label_text` (texto de la etiqueta que fija el motor) y `reasons` |
| `provisional`, `synthetic_fixture` | Banderas para los banners |
| `summary_es`, `summary_en` | Resúmenes ejecutivos |
| `strategies[]` | `name`, `freq_critical`, `severity_p90`, `severity_cvar90`, `worst_year`, `n_valid`, `n_expected`, `evidence` (ya formateados con su unidad) |
| `ranking` | `status`, `rows[]`, `weights`, `weight_coverage`, `stability.{flag, flag_text, conflicts[]}` |
| `limitations[]`, `missing_data[]`, `field_conditions[]` | Listas de texto |
| `annex` | `methodology`, `assumptions[]`, `sources[]`, `indicators[]`, `scenarios[]`, `cycles[]`, `references[]` |

## Qué garantiza la plantilla

- Texto fijo «No es una recomendación automática» en el idioma del informe (y en inglés en `es+en`).
- Banner de modo con la etiqueta del motor y banners de provisionalidad.
- Estabilidad con texto y marca (no solo color) y la nota de que mide sensibilidad a los pesos.
- `run_id`, `code_version` y los hashes de §25 al pie.
- Anexo con metodología, supuestos, fuentes (con «NASA»/«No es NASA»), procedencia, escenarios, resultados por ciclo y referencias.

## Privacidad

- `internal`: contenido según el acceso de la persona usuaria.
- `public`: el **backend** debe omitir nombre de agricultor, código de parcela y ubicaciones más finas que la zona; la plantilla no recibe esos datos en ese caso. La regla CSS `.privacy-public [data-private]` es solo una segunda barrera.
- La prueba T-A·J con PDF real (cero coordenadas, correos o nombres) es de R3.

## Pendiente

R3 debe confirmar el esquema del `report_model`, el DTO de secciones y el renderizado con WeasyPrint (Pango en la imagen). Hasta entonces la vista previa de la SPA usa `ReportDTO.sections/annex` y no sustituye al PDF.
