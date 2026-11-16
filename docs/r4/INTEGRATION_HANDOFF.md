# Entrega de integración de R4

## Alcance

R4 entrega el frontend y sus puntos de conexión para incorporar R1, R2, R3 y el entorno integrado de S2. No implementa el backend ni sustituye los contratos de esos equipos. El OpenAPI presente es un borrador local derivado de la arquitectura del proyecto; no es el contrato oficial de R3.

## Artefactos listos

| Necesidad | Artefacto R4 | Alcance comprobado |
|---|---|---|
| OpenAPI | `contracts/openapi.v0.draft.yaml` | Define las rutas `/v1` derivadas del documento principal; la auditoría local encontró 30 rutas y 196 referencias internas resueltas. Las discrepancias SPEC-01–SPEC-06 están registradas en `CONTRACT_RECONCILIATION.md`. |
| Tipos TypeScript | `apps/web/src/api/types.gen.ts` | Generados desde el OpenAPI borrador mediante `npm run web:types`; no editar a mano. Build y tests también regeneran los tipos. |
| Cliente API | `apps/web/src/api/client.ts` y `apps/web/src/api/config.ts` | `openapi-fetch` tipado con `paths`, llamadas bajo `/v1` y URL configurable. |
| Mock de vista local | `apps/web/src/api/mock-api.ts` | Solo Vite en modo `mock`; fuerza llamadas same-origin, identifica sus datos, evita resultados científicos ficticios y devuelve 501 en operaciones sin fixture aprobado. |
| Entorno conectable | `apps/web/.env.example`, `apps/web/vite.config.ts` | Proxy `/v1` mediante `MILPA_API_PROXY` (por defecto `http://127.0.0.1:8000`) o base URL del navegador mediante `VITE_MILPA_API_BASE_URL`. No incluye secretos ni dirección real de S2. |

## Uso local

En la raíz del repositorio:

```powershell
npm install
npm run web:dev:mock
```

Abre `http://localhost:5173` o la dirección que muestre Vite si ese puerto está ocupado. El modo mock sirve para inspeccionar la interfaz sin backend. Las operaciones científicas, autenticación y generación de informes requieren respuestas de sus equipos y quedan como insuficientes/pendientes.

Para apuntar al API integrado cuando S2/R3 comparta su dirección, copia `apps/web/.env.example` a `apps/web/.env.local`, coloca allí `MILPA_API_PROXY` o `VITE_MILPA_API_BASE_URL` según el gateway, y ejecuta `npm run web:dev`. `.env.local` está ignorado por Git.

## Recepción de entregables

1. **R3:** entregar OpenAPI oficial versionado, mock de API, esquema de errores, autenticación, URLs disponibles y DTOs de zonas, calidad, carga, ejecuciones e informe. Comparar primero con `CONTRACT_RECONCILIATION.md` y `PRODUCT_TRACEABILITY.md`; generar tipos desde el archivo oficial mediante `MILPA_OPENAPI_SPEC` solo tras registrar y resolver las diferencias que alteren contratos.
2. **R2:** entregar etiquetas, reglas de evidencia/procedencia, payloads de indicadores y estructuras de ranking/estabilidad. R4 debe comprobar que los DTOs muestran estado, fuente y limitaciones requeridos por el documento principal.
3. **R1/R2:** entregar catálogo, metadatos de fuente y fixtures autorizados `data/demo/` más `EXPECTED.json` y hashes. R4 no crea sustitutos científicos; UX-08 y los casos T-A·A–J dependen de esos artefactos.
4. **S2:** entregar URL del entorno integrado, esquema de autenticación y configuración de red/CORS si aplica. El proxy y el base URL ya son configurables; la conexión real no se ha probado ni se declara establecida.

## Verificación de R4

```powershell
npm run web:types
npm run web:test
npm run web:build
npm run web:test:e2e
```

En esta entrega, generación de tipos, Vitest/copy-linter y build pasaron. La vista local mock respondió HTTP 200 en `localhost:5174`; `/v1/zones` devolvió la zona marcada MOCK y una ruta de ranking sin fixture devolvió 501. Playwright se inició, pero no terminó con resultado verificable en este entorno. Los casos T-A·A–J no se aprueban hasta contar con fixtures de R1/R2 y las respuestas oficiales necesarias.

R4 se considerará conectado cuando el contrato oficial esté conciliado, los tipos se generen desde él, el API de S2/R3 responda en el entorno acordado, y las pruebas de contrato, interfaz y accesibilidad estén verificadas con los artefactos reales de los equipos.
