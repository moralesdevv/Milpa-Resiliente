# Agregar una región (README §23, principio P4 «configuración sobre código»)

Una región nueva se agrega **con archivos, sin tocar `packages/`**. Hoy existe un *region pack* de ejemplo (`regions/pilot_corredor_seco.yaml`) con todo en `pending` y una región alterna **sintética rotulada** (`regions/example_alt_region.yaml`) para la prueba de reproducibilidad G.

## Pasos
1. Crear `regions/<codigo>.yaml` con zona, archivo de polígono y `agri_year_start` (MM-DD). **Todo campo con efecto agronómico es obligatorio en modo `production`; `pending` solo se admite en `sandbox`** (`milpa-etl check-catalog catalogs/crops.yaml --mode production` lo comprueba para los catálogos; para el region pack aún no hay validador: pendiente de R1).
2. Colocar el polígono en `regions/<zona>.geojson` (zona de análisis, nunca una parcela; sin coordenadas privadas).
3. Completar los catálogos con **cita** (`catalogs/*.yaml`): cultivos, variedades, Kc/fenología, ventanas críticas, umbrales. Un valor sin cita queda `pending` y la corrida se rotula *provisional* (P9). **No se inventan valores.**
4. Registrar fuentes y procedencia: `milpa-etl fetch power|imerg` → `curate` → `validate` → `register manifest|zone|provenance` (rol propietario).
5. `milpa-etl seed catalog --catalog catalogs/crops.yaml` carga los catálogos de forma idempotente y registra `ref.catalog_release`.
6. `make reproduce` debe seguir verificando `data/demo` sin cambios: una región nueva no altera el paquete congelado.

## Qué decide cada rol
R1: región, catálogos con cita, reglas de evidencia. R2: método (modo A/B, Pef, umbrales). R3: no contiene configuración científica.
