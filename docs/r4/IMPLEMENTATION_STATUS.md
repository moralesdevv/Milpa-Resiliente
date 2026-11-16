# Estado de implementación R4

Actualizado: 2026-11-15. Sustituye la versión del 2026-11-14.

## Qué es y qué no es este avance

- Todo lo verificado abajo se ejecutó contra un **servidor simulado con un fixture sintético rotulado** (`apps/web/src/api/mock-fixture.ts`). Sus valores están inventados para ejercitar la interfaz: no son datos del piloto, ni de R1/R2, ni resultados científicos. Cada indicador del fixture sale `provisional`, evidencia C y con el aviso «Fixture sintético de prueba».
- No existen `data/demo/`, `EXPECTED.json`, OpenAPI oficial, API de R3 ni motor de R2 en este repositorio. Por eso **no se declara cumplido** ningún criterio que dependa de ellos (ver «Sigue pendiente»).
- El contrato (`contracts/openapi.v0.draft.yaml`) sigue siendo un **borrador local de R4**; se amplió con los DTO que la interfaz necesita (job, run, calidad de datos, historial, catálogo, contexto de zona, subida de suelo, etc.), todos marcados como forma propuesta que R3/R2 deben confirmar.

## Estado por tarea

| ID | Estado | Implementado | Sigue pendiente |
|---|---|---|---|
| UX-01 | Documentado | Personas, historias, glosario y matriz de trazabilidad | Alinear con contratos oficiales |
| UX-02 | Implementado sobre el borrador | `Indicator` (completo y compacto), `EvidenceBadge`, `ProvenancePanel`, `ProvisionalBanner`, `ScenarioBadge`, `ScenarioPicker`, `AdaptationToggle`, `ScenarioLauncher`, `StabilityMeter`, estados Loading/Empty/Error/Insufficient, `RunHeader` | `GET /v1/provenance/{ip_id}`: el `Indicator` del borrador no trae `ip_id`, así que el panel usa la procedencia embebida |
| UX-03 | Implementado sobre el borrador | Zona, celdas con pesos y mapa Leaflet (celdas y ubicación generalizada), cultivos con marca «Pendiente de validar», fuentes con institución y «NASA / No es NASA», cobertura por variable y año, contraste entre fuentes, suelo por propiedad, subida de CSV con errores por fila, declaraciones con base, borrado de parcela con confirmación, Soil VoI con sus estados, inicio de sesión | Lista de parcelas (no hay contrato); consentimiento; proveedor real de teselas (variables `VITE_MAP_TILE_URL` y `VITE_MAP_ATTRIBUTION`) |
| UX-04 | Implementado sobre el borrador | Historial de 25 años (gráfico, tendencias, tabla), cabecera de modo con razones, tarjetas por estrategia con tabla por ciclo (`n_valid`/`n_expected`, sensibilidad de umbral y de Pef, bandera `peff_sensible_al_metodo`), heatmap de cuatro estados con patrón, marca y texto, ventana consistente, regla `any/sum`, umbrales usados, gráfico por decena con bandas de etapa, decenas sobre umbral marcadas, vista acumulada y asociación exploratoria | Etiquetas y payloads reales de R2/R3 |
| UX-05 | Implementado sobre el borrador | Catálogo de estrategias con ejes de cambio, lanzamiento y seguimiento de trabajos de escenarios, pesos con reajuste proporcional (suma 1) y recálculo automático, estado por criterio, ranking con soporte común, criterios excluidos, `weight_coverage`, tabla parcial si es insuficiente, barras por criterio, `decision_log`, explicaciones por pares, estabilidad de cuatro estados, conflictos, inversiones de posición frente a BASE | Parámetros de estabilidad: la interfaz solo envía `mode` y `seed`; el resto lo decide el backend |
| UX-06 | Parcial | Formulario, seguimiento del trabajo hasta obtener `report_id`, vista A4 con secciones y anexo del `ReportDTO`, resumen en inglés, hashes de la corrida, enlace al PDF del backend, nota de privacidad. **Plantilla Jinja2 + CSS de impresión entregada** (`apps/api/templates/`) | No se ha generado ni inspeccionado ningún PDF real; el contrato del `report_model` es de R2/R3 |
| UX-07 | Parcial | ES/EN con las mismas claves, sin textos fijos en los componentes, ESLint, linter de textos, axe sin violaciones automáticas en las cuatro pantallas con datos, sin desbordamiento horizontal a 375 y 768 px, teclado en navegación y procedencia | Revisión manual de accesibilidad (lector de pantalla, zoom, contraste en modo de alto contraste); axe cubre solo una parte de WCAG 2.1 AA y **no demuestra conformidad** |
| UX-08 | Parcial | T-UI en Playwright; T-A·A a T-A·J con la parte de interfaz sobre el fixture sintético; pruebas de componentes y del simulado en Vitest | T-A sobre `data/demo/` congelado; `make reproduce`; PDF real; segundo usuario y borrado en disco (R3). Quedan 3 `test.fixme` con su motivo |
| UX-09 | No ejecutado | `USABILITY_PLAN.md` y `USABILITY_REPORT.md` (plantilla vacía) | Sesiones reales con técnicos o agricultores (DP-15). No hay resultados y no se inventan |
| UX-10 | Parcial | `DEMO_SCRIPT.md` con el recorrido que ya se puede hacer con el simulado | Ensayo sobre datos congelados |

## Verificaciones realmente ejecutadas (2026-11-15)

| Comando | Resultado |
|---|---|
| `npm run lint --workspace @milpa-resiliente/web` (ESLint) | Sin errores ni avisos |
| `npm run typecheck --workspace @milpa-resiliente/web` (`tsc -b`) | Sin errores |
| `npm run web:test` (tipos + Vitest + linter de textos) | 26 pruebas Vitest y 8 del linter de textos, todas verdes |
| `npx playwright test` (Chromium 1217 preinstalado, vía `PLAYWRIGHT_CHROMIUM_EXECUTABLE`) | 25 verdes, 3 `fixme` |
| `npm run web:build` | Verde; aviso de tamaño de bloque (ECharts) |

Qué cubren las 25 pruebas de Playwright: estados de interfaz (vacío, error `SCENARIO_NOT_COMPUTED`, insuficiente, provisional, teclado, procedencia); axe sobre las cuatro pantallas; sin desbordamiento a 375 y 768 px; y T-A·A, B, C, D (i, ii, iii), E, F (parte de interfaz), G (parte de interfaz), H, I y J (parte de interfaz).

Qué encontraron: la primera ejecución real de axe halló una violación (`label-content-name-mismatch` en el enlace de marca) y problemas de contraste en la marca «Pendiente» y en unidades de indicadores; la de diseño halló desbordamiento horizontal causado por texto oculto dentro de tablas con scroll. Todo se corrigió.

## Sigue pendiente (no depende de R4)

1. OpenAPI oficial y servidor simulado de R3: confirmar las formas del borrador (SPEC-01 a SPEC-06 y los DTO nuevos).
2. `data/demo/`, `EXPECTED.json`, catálogos y reglas de evidencia de R1; payloads y textos de R2.
3. Generación del PDF por R3 (WeasyPrint) y su verificación (T-A·F, T-A·J con PDF).
4. `make demo` y `make reproduce` (R3): el `Makefile` actual solo trae los objetivos del frontend.
5. Segundo usuario, RLS y borrado de archivos (T-S, T-A·J).
6. Sesiones de usabilidad (UX-09) y revisión manual de accesibilidad.
7. Comprobar los DP-09 (umbrales de comunicación de estabilidad) y los DP de umbrales: la interfaz no los decide.
8. `npm audit` reporta vulnerabilidades en dependencias de desarrollo; sin revisar ni resolver aquí.

## Cómo ejecutar

```bash
npm ci
npm run web:dev:mock      # interfaz con el simulado y el fixture sintético
npm run web:test          # tipos + Vitest + linter de textos
npm run lint --workspace @milpa-resiliente/web
npm run web:test:e2e      # Playwright (T-UI y T-A); PLAYWRIGHT_CHROMIUM_EXECUTABLE si no puede instalar navegadores
```

En el simulado, mutaciones (subir suelo, declarar, borrar parcela, lanzar escenarios, generar informe) piden iniciar sesión; el simulado acepta cualquier correo y contraseña no vacíos y no guarda nada.
