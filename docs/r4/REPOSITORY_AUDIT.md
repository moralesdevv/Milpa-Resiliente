# Auditoría inicial de R4 — MILPA RESILIENTE 3.3

Fecha de revisión: 2026-11-14  
Estado: auditoría documental previa a cambios de producto o contratos.

## Fuentes y alcance de la revisión

- Se leyó el PDF **MILPA RESILIENTE 3.3 — Arquitectura técnica integral del MVP** completo: 110 páginas, 29.848 palabras extraíbles.
- Se revisó el prompt maestro de implementación de R4 adjunto a la solicitud.
- Se inspeccionó el árbol del repositorio, sus archivos ocultos y el estado de Git.
- Se respetó la exclusión del texto introductorio del reto climático indicada en el prompt. La revisión usa la definición de producto, sus funcionalidades y su arquitectura técnica.

El PDF se declara a sí mismo una especificación de diseño: sus decisiones marcadas como [Propuesto], [Pendiente] o [Verificar] no constituyen validación ni evidencia de que exista una implementación.

## Estado del repositorio

El directorio de trabajo solo contiene `.git`; no hay archivos versionados, archivos sin seguimiento ni commits. No se encontró `AGENTS.md`.

| Elemento | Estado actual | Requisito documental | Acción necesaria |
|---|---|---|---|
| Frontend | Ausente; no hay `apps/web`, dependencias ni configuración | SPA React 18 + TypeScript + Vite; tipos desde OpenAPI, `openapi-fetch`, TanStack Query, filtros en URL e i18n | Integrar después de recibir OpenAPI v0, mock y tipos de R3; no duplicar DTOs |
| Pantalla 1 — Mi zona | Ausente | Zona/celdas, fuentes y calidad, suelo por propiedad, carga/declaración y Soil VoI | Requiere endpoints y DTOs de R1–R3; preservar privacidad |
| Pantalla 2 — Cómo cambió el calendario | Ausente | Historial, riesgo por etapas, gráfico por decena y heatmap | Requiere series/metadatos de R1 y respuestas de R2/R3 |
| Pantalla 3 — Laboratorio de rotaciones | Ausente | Estrategias, ranking con soporte común, pesos, estabilidad y escenarios | Requiere catálogos, resultados calculados, contratos y mock |
| Pantalla 4 — Informe de decisión | Ausente | Vista bilingüe, página A4, anexo y generación PDF del backend | Requiere plantilla integrada con mecanismo de informes de R3 |
| Componentes | Ausentes | Indicator, evidencia, procedencia, estados, escenarios, gráficos y suelo | Implementar contra los tipos generados; no calcular ciencia en UI |
| API | Ausente | REST `/v1`, autenticación, autorización, zonas, parcelas, corridas y reportes | R3 es dueño; no inventar rutas ni cambiar DTOs |
| OpenAPI, tipos y mock | Ausentes | OpenAPI v0, servidor mock y tipos TypeScript generados en Fase 0 | Dependencia crítica de R3; registrar cualquier variación cuando se reciba |
| Gráficos y mapa | Ausentes | ECharts para decenas/heatmap; Leaflet para zona y celdas generalizadas | Requiere DTOs R2/R3; no incluir geometría exacta |
| Informe | Ausente | Backend genera PDF determinista; informe `internal` o `public` | Entregar/integrar plantilla a R3; no construir API ni motor PDF paralelo |
| Internacionalización y accesibilidad | Ausentes | `react-i18next` es/en, glosario, teclado, contraste, descripciones de gráficos; WCAG 2.1 AA como objetivo | Implementar y verificar por pruebas automáticas y revisión manual; no declarar conformidad sin evidencia |
| Pruebas y CI | Ausentes | Vitest, Playwright, axe, linter de textos, T-A·A–J y verificaciones transversales | R3 debe aportar entorno/mock y fixtures; ninguna prueba se reportará aprobada sin ejecución |
| Datos congelados | Ausentes | `data/demo/`, fixtures sintéticos rotulados y `EXPECTED.json` | Dependencia de R1/R2; no sustituir con datos ficticios presentados como piloto |
| Documentación R4 | Ausente | Trazabilidad, metodología de usabilidad, guion de demo y guía de ejecución | Preparar los documentos R4 que no dependen del backend; dejar dependencias explícitas |

## Registro de discrepancias previo a implementación

| ID | Discrepancia observada | Requisito relacionado | Efecto | Tratamiento antes de cambiar contratos o funciones |
|---|---|---|---|---|
| AUD-01 | El repositorio está vacío frente al monorepo especificado en §23 y a `apps/web` pedido para R4 | UX-01–UX-10; §23, §26–§29 | No hay código funcional existente que preservar ni forma de verificar una integración | Registrar esta auditoría primero; después construir solo artefactos R4 independientes. No afirmar que el resto de equipos no haya trabajado fuera de este checkout |
| AUD-02 | No hay OpenAPI v0, DTOs, enums generados, cliente, mock ni payloads | UX-02–UX-08; §13, §15–§17, §26–§27 | Una app que declare tipos manuales o rutas propias contradiría P8 y las reglas de integración | No crear contratos ni endpoints paralelos. Esperar/solicitar artefactos R3/R2; documentar incompatibilidades cuando estén disponibles |
| AUD-03 | No hay datos demo, procedencia, catálogos citados ni `EXPECTED.json` | UX-03–UX-06, UX-08, UX-10; §8–§9, §19, §21, §25, §29 | No se pueden renderizar indicadores reales ni ejecutar T-A sobre datos congelados | UX y fixture no deben inventar valores agronómicos; preparar estados vacíos/insuficientes y documentos. R1/R2 deben entregar datos congelados y metadatos |
| AUD-04 | No hay backend, autenticación, RBAC/RLS, almacenamiento ni generador PDF | UX-03, UX-06, UX-08; §13, §16, §22–§24 | No es posible validar cargas, permisos, borrado, informes ni privacidad integral | R3 conserva titularidad de API, contratos, autorización, PDF y CI. R4 entrega plantilla y consume la API cuando exista |
| AUD-05 | La arquitectura lista valores y parámetros pendientes (DP-01–DP-17) y afirma que aún no están validados | UX-03–UX-06; §1, §11, §19–§21, §30 | No deben convertirse en decisiones del frontend ni en resultados definitivos | Usar estados `pending`, sandbox y provisionalidad definidos; sin cita no crear umbral ni declarar Modo B, VoI o retraso de lluvias calculable |
| AUD-06 | El plan de pruebas §24 es un plan, no prueba implementada o superada | UX-08 y aceptación §29 | Ningún criterio puede marcarse como verde por su sola descripción | Conservar IDs T-A·A–J/T-UI/T-C/T-S; reportar estado ejecutado solo con evidencia de ejecución posterior |
| AUD-07 | La guía de ejecución §31 describe el objetivo futuro del repositorio y explícitamente no prueba que funcione | UX-10 y criterios de instalación | No hay `make demo`, `make reproduce` ni entorno que verificar | Implementar/documentar una ruta reproducible cuando existan entregables R1–R3; ahora registrar como brecha |

No se encontró una contradicción entre implementaciones locales y el PDF: no hay implementaciones locales que comparar. Las brechas anteriores son ausencias del checkout, no evidencia de que los contratos estén en conflicto. Este informe se crea antes de cualquier cambio funcional o contractual.

## Decisiones del documento que condicionan toda UX

1. El producto compara consistencia ante condiciones adversas; no es pronóstico, simulador de rendimiento ni recomendación automática (§2, §11, §19).
2. Modo A (exposición climática) y Modo B (balance hídrico de zona radicular) son modelos, etiquetas y DTOs distintos. El motor decide; la UI solo muestra su `mode`/`label` (§5, §11.1, §15, X01).
3. Ningún número se muestra fuera de `Indicator` con procedencia y evidencia; las cifras desconocidas no son cero. La evidencia se propaga como mínimo y no certifica por sí sola calidad (§5, §15, §21, CT-01/CT-06).
4. Las decenas, cohortes, ciclos y estrategias conservan las unidades de análisis del motor. Fecha de siembra no equivale a rotación; cohortes multianuales pueden solaparse (§11.6, §11.9, T-A·H).
5. Celdas del heatmap: `critical`, `non_critical`, `insufficient_data`, `not_evaluable`; se diferencian por patrón y texto además de color (§13, §15, §17, T-UI).
6. El ranking usa soporte común y `weight_coverage`; un criterio que falta se excluye para todas las estrategias. Los pesos pueden modificarse, pero una estrategia no gana por tener menos datos (§11.11, T-A·I).
7. Estabilidad tiene cuatro valores de enum: `stable`, `moderate`, `unstable`, `insufficient`; mide sensibilidad a pesos, no probabilidad de ser la mejor (§11.12, §13, §15, T-P16).
8. La grilla estándar de escenarios tiene 27 combinaciones y 18 sensibilidades de humedad (45 total); escenarios no calculados devuelven `SCENARIO_NOT_COMPUTED`/409 y requieren trabajo, no cálculo silencioso (§16, §19, T-A·C).
9. Solo valores citados habilitan uso científico. Donde falte evidencia se degrada el estado, se marca provisional o se bloquea el resultado; no se rellena con valores inventados (§5, §11, §30).
10. Las parcelas no guardan ni exponen geometría exacta en el MVP; la ubicación visible se generaliza y el informe público omite persona, código de parcela y ubicación más fina que la zona (§13, §18, §22, T-A·J).
11. `internal` y `public` son salidas distintas; ambos excluyen coordenadas exactas (§18, §22).
12. Las etiquetas científicas y estados vienen de contratos y motor; OpenAPI genera tipos; la UI no reimplementa cálculos ni las conclusiones (§5, §15–§17, §21).

## Siguiente puerta de integración

Para que UX-02–UX-08 consuman datos reales y sean comprobables se necesitan, como mínimo: OpenAPI v0 y enums/DTOs de R2/R3; mock con respuestas ejemplo; datos congelados, catálogos, reglas de evidencia y procedencia de R1/R2; entorno de backend y mecanismo de informe de R3. Cuando lleguen, comparar esos artefactos contra los requisitos referenciados en `PRODUCT_TRACEABILITY.md` y actualizar este registro antes de cualquier ajuste de contrato.
