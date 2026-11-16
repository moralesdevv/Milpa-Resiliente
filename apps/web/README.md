# MILPA RESILIENTE — frontend R4 (borrador local)

Esta SPA consume únicamente rutas documentadas en el PDF mediante un OpenAPI local marcado como borrador. No contiene datos científicos demo ni reemplaza contratos R1/R2/R3.

## Requisitos

- Node.js 22 o posterior.
- El API R3 en `http://127.0.0.1:8000` solo es necesario para consultar datos; no hace falta para abrir la vista frontend.

## Instalación y ejecución

Desde la raíz del repositorio:

```powershell
npm install
$env:MILPA_API_PROXY = "http://127.0.0.1:8000"
npm run web:dev
```

Vite muestra en la terminal la dirección del frontend, normalmente `http://127.0.0.1:5173`. **El puerto 8000 es el API, no la página web.** La ruta `/v1` se reenvía al API configurado. Sin el API, la interfaz puede abrirse, pero las consultas mostrarán estados de error o información pendiente. La aplicación no crea datos demo ni respuestas científicas.

### Tutorial rápido: abrirlo en local

1. Abre PowerShell en la carpeta `C:\Users\dmnjo\Downloads\R4`.
2. Instala las dependencias y arranca el frontend:

   ```powershell
   npm install
   npm run web:dev
   ```

3. Abre en el navegador la URL que imprime Vite, normalmente `http://127.0.0.1:5173`.
4. Para cargar datos, R3 también debe estar iniciado en `http://127.0.0.1:8000`. Sin ese backend, la interfaz puede abrir, pero las consultas mostrarán estados de error o información pendiente; no usa datos demo inventados.

El servidor de desarrollo no genera tipos al arrancar. `openapi-typescript` sí se necesita para generar los tipos usados por la comprobación de TypeScript, las pruebas y la compilación de producción.

### Mock local de R4

Para ver las pantallas sin iniciar R3, desde la raíz ejecuta:

```powershell
npm run web:dev:mock
```

Abre la dirección `Local` que imprime Vite (normalmente `http://localhost:5173`). El mock está activo solo en este modo y el banner de la interfaz lo identifica. Devuelve una zona rotulada MOCK y estados vacíos/insuficientes; no inventa resultados científicos, datos de piloto, rankings ni informes. Las operaciones que dependen de una salida real responden `501 MOCK_ROUTE_PENDING`.

### Conexión con el entorno integrado

El modo normal conserva el proxy `/v1` hacia `MILPA_API_PROXY` (por defecto `http://127.0.0.1:8000`). Para apuntar al gateway entregado por S2/R3, crea `apps/web/.env.local` a partir de `.env.example` y configura allí su URL. `.env.local` no se versiona. El frontend usa rutas `/v1` del borrador OpenAPI; al recibir el contrato oficial se compara primero con `docs/CONTRACT_RECONCILIATION.md`.

## Tipos y compilación

```powershell
npm run web:types
npm run web:build
```

`web:types` genera `src/api/types.gen.ts` desde `contracts/openapi.v0.draft.yaml`. El archivo generado no debe editarse a mano. Al recibir el contrato oficial, guárdalo en el repositorio y define `MILPA_OPENAPI_SPEC` con su ruta antes de `npm run web:types`; compara primero el contrato con `docs/CONTRACT_RECONCILIATION.md`.

## Verificaciones disponibles

```powershell
npm run web:test:copy
npm run web:test
npm run web:test:e2e
```

El linter de textos corre con Node.js; Vitest, Playwright, ECharts y la compilación usan las dependencias instaladas con `npm install`. Los tests T-A·A–J necesitan los datos congelados y `EXPECTED.json` de R1/R2; no se fabrican fixtures científicos en R4.

## Pantallas

- `/my-zone`: zonas, territorio, fuentes, calidad, suelo y acceso al Soil VoI.
- `/calendar`: filtros compartibles en URL, indicadores de riesgo, heatmap y gráfico por decena.
- `/rotations`: combinaciones calculadas, pesos editables y solicitud de ranking a R3.
- `/report`: solicitud del informe y visualización del PDF generado por R3.

Cuando falte un campo contractual, la pantalla lo identifica como pendiente o insuficiente. No se muestran geometrías de parcelas ni se ejecutan cálculos científicos en el navegador.
