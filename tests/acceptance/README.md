# Pruebas de aceptación (T-A)

`acceptance.spec.ts` contiene T-A·A a T-A·J del §29. Se ejecutan con Playwright desde `apps/web`:

```bash
npm run web:test:e2e
```

**Alcance real.** Corren contra el servidor simulado de R4 y su fixture **sintético rotulado** (`apps/web/src/api/mock-fixture.ts`), no contra `data/demo/` congelado ni contra el backend de R3. Comprueban lo que le toca a la interfaz. Lo que depende del backend o de datos reales queda como `test.fixme`, con su motivo:

| Prueba | Parte de interfaz | Pendiente (dueño) |
|---|---|---|
| T-A·F | Secciones, anexo, inglés, `run_id`, hashes, aviso fijo y enlace al PDF | El PDF real (R3) |
| T-A·G | La corrida muestra los cinco identificadores | `make reproduce`, `EXPECTED.json`, región alterna (R1/R3) |
| T-A·J | Informe público sin parcela, sin coordenadas finas ni correos, borrado de parcela | Segundo usuario, RLS, borrado de Parquet y PDFs (R3) |

Cuando existan `data/demo/` y `EXPECTED.json`, hay que repetir estas pruebas contra ellos y comparar con `EXPECTED.json`; hasta entonces no valen como aceptación de «terminado».

Si Playwright no puede descargar su navegador: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=<ruta a chrome> npm run web:test:e2e`.
