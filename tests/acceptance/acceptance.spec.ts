/**
 * Pruebas de aceptación T-A·A a T-A·J (MILPA RESILIENTE 3.3, §29).
 *
 * ALCANCE HONESTO: corren contra el servidor simulado de R4 con un FIXTURE
 * SINTÉTICO rotulado (apps/web/src/api/mock-fixture.ts), no contra `data/demo/`
 * congelado de R1/R2 ni contra el backend de R3. Verifican lo que le toca a la
 * interfaz. Las partes que dependen del backend real quedan como `test.fixme`
 * con su motivo.
 */
import { expect, test } from "@playwright/test";

import { COMBINED, PARCEL, RUN, RUN_NO_MATRIX, ZONE, expectNoProhibitedClaims, resetMock, signIn } from "./helpers";

const calendarUrl = `/calendar?runId=${RUN}&scenarioId=BASE&adaptation=none`;
const rotationsUrl = `/rotations?runId=${RUN}&scenarioId=BASE&adaptation=none`;
const zoneUrl = (run: string) => `/my-zone?zoneId=${ZONE}&parcelId=${PARCEL}&runId=${run}`;

test.beforeEach(async ({ page }) => {
  await resetMock(page);
});

test("T-A·A suelo desconocido: Modo A, sin «agua disponible», suelo desconocido y VoI evaluable", async ({ page }) => {
  await page.goto(calendarUrl);
  await expect(page.getByTestId("mode-label")).toHaveText("Indicador de exposición climática");
  await expect(page.getByTestId("run-header")).toContainText("capacidad de agua disponible");
  await expectNoProhibitedClaims(page);
  expect(await page.locator("body").innerText()).not.toMatch(/agua disponible para las raíces/i);

  await page.goto(zoneUrl(RUN));
  const rows = page.locator('[data-testid="soil-table"] tbody tr');
  await expect(rows).toHaveCount(5);
  for (const row of await rows.all()) await expect(row).toContainText("Desconocido");
  await page.getByRole("button", { name: "Consultar valor de información" }).click();
  await expect(page.getByText("Aplicable")).toBeVisible();
});

test("T-A·B decena seca oculta: el ciclo se marca y el acumulado es suficiente", async ({ page }) => {
  await page.goto(calendarUrl);
  const chart = page.getByTestId("dekad-chart");
  await expect(chart).toBeVisible();
  await expect(page.getByTestId("over-threshold-note")).toContainText("7 (");
  await expect(chart.locator("tr.row-over-threshold")).toHaveCount(1);
  await expect(chart.getByText("Umbral provisional").or(chart.getByText(/provisional/i)).first()).toBeVisible();

  await chart.getByLabel("Acumulado").check();
  const lastCumulative = chart.locator("details", { hasText: "Tabla de valores acumulados" }).locator("tbody tr").last();
  await chart.locator("summary", { hasText: "Tabla de valores acumulados" }).click();
  const numbers = (await lastCumulative.innerText()).match(/\d+(?:[.,]\d+)?/g)?.map((n) => Number(n.replace(",", "."))) ?? [];
  // fila: índice, Pef acumulada, ETc acumulada → la lluvia efectiva acumulada supera la demanda acumulada.
  const [, pefCumulative, etcCumulative] = numbers;
  expect(pefCumulative).toBeGreaterThan(etcCumulative);
});

test("T-A·C escenario combinado: parámetros, humedad, inversiones frente a BASE y sensibilidad Hea", async ({ page }) => {
  await page.goto(`/rotations?runId=${RUN}&scenarioId=${COMBINED}&adaptation=none`);
  const badge = page.locator(".scenario-badge").first();
  await expect(badge).toContainText("Escenario sintético");
  await expect(badge).toContainText("T+2_P-20_D+20_Hrh");
  await expect(badge).toContainText("Humedad relativa constante");
  await expect(badge).toContainText("Sin regla de adaptación");
  await expect(page.getByTestId("inversions")).toContainText("El orden cambia respecto de BASE");
  await expect(page.locator('[data-testid="inversions"] tr[data-change="up"], [data-testid="inversions"] tr[data-change="down"]').first()).toBeVisible();
  // La variante Hea aparece como sensibilidad, junto a la principal.
  await expect(page.locator("select option", { hasText: "T+2_P-20_D+20_Hea" })).toHaveCount(1);
  await expectNoProhibitedClaims(page);
});

test.describe("T-A·D pH hipotético", () => {
  test("(i) pH desconocido con matriz: valores rotulados «valor hipotético, no medido»", async ({ page }) => {
    await page.goto(zoneUrl(RUN));
    await page.getByRole("button", { name: "Consultar valor de información" }).click();
    const panel = page.locator(".voi-panel");
    await expect(panel).toContainText("Ranking sensible");
    await expect(panel.locator(".hypothetical-label").first()).toHaveText("valor hipotético, no medido");
    await expect(panel.locator(".hypothetical-card")).toHaveCount(2);
  });

  test("(ii) sin matriz: información insuficiente, sin recomendar laboratorio y con la cita que falta", async ({ page }) => {
    await page.goto(zoneUrl(RUN_NO_MATRIX));
    await page.getByRole("button", { name: "Consultar valor de información" }).click();
    const panel = page.locator(".voi-panel");
    await expect(panel).toContainText("Información insuficiente");
    await expect(panel).toContainText("matriz de tolerancia de pH con cita");
    await expect(panel).not.toContainText("Se recomienda obtener análisis de laboratorio");
  });

  test("(iii) pH medido: «pH medido» y ningún veredicto de estabilidad", async ({ page }) => {
    await page.goto(zoneUrl(RUN));
    await signIn(page);
    await page.locator('input[type="file"]').setInputFiles({
      name: "suelo.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("parcel_code,sample_date,ph,ph_method,om_pct\nP-014,2025-03-12,5.8,H2O_1:2.5,\n"),
    });
    await page.getByRole("button", { name: "Validar y subir" }).click();
    await expect(page.getByTestId("upload-result")).toContainText("ph (1)");
    await expect(page.locator('[data-property="ph"]')).toContainText("Medido");
    // T-P10 en la interfaz: materia orgánica sigue desconocida.
    await expect(page.locator('[data-property="om_pct"]')).toContainText("Desconocido");
    await expect(page.locator("#voi-title").locator("xpath=ancestor::section")).toContainText("pH medido");
    await expect(page.locator(".voi-panel")).toHaveCount(0);
  });
});

test("T-A·E prioridades y estabilidad: el orden cambia, la estabilidad se recalcula y el aviso está siempre", async ({ page }) => {
  await page.goto(rotationsUrl);
  const firstRow = page.locator('[data-testid="ranking-table"] tbody tr').first();
  await expect(firstRow).toBeVisible();
  const before = await firstRow.getAttribute("data-strategy");
  const flagBefore = await page.getByTestId("stability-meter").getAttribute("data-flag");
  expect(["stable", "moderate", "unstable", "insufficient"]).toContain(flagBefore);

  await page.getByTestId("weight-water").fill("0.05");
  await expect(page.locator('[data-testid="ranking-table"] tbody tr').first()).not.toHaveAttribute("data-strategy", before ?? "");
  await expect(page.getByTestId("stability-note")).toContainText("Mide sensibilidad a los pesos, no la probabilidad de ser la mejor");
  const flagAfter = await page.getByTestId("stability-meter").getAttribute("data-flag");
  expect(["stable", "moderate", "unstable", "insufficient"]).toContain(flagAfter);
  await expect(page.getByTestId("conflicts")).toBeVisible();
  await expect(page.getByTestId("pair-explanations")).toBeVisible();
  // La suma de pesos se mantiene en 1 al mover un control.
  await expect(page.locator(".weight-sum")).toContainText("1.00");
});

test("T-A·F informe (parte de interfaz): secciones, anexo, inglés, run_id, hashes, aviso y PDF del backend", async ({ page }) => {
  await page.goto(`/report?runId=${RUN}`);
  await signIn(page);
  await page.getByLabel("Privacidad del informe").selectOption("public");
  await page.getByRole("button", { name: "Solicitar informe al backend" }).click();
  const sheet = page.getByTestId("report-sheet");
  await expect(sheet).toContainText("Resumen ejecutivo");
  await expect(sheet).toContainText("Anexo técnico");
  await expect(sheet).toContainText("Supuestos y sensibilidad");
  await expect(sheet.locator('[lang="en"]').first()).toContainText("Comparison of three strategies");
  await expect(sheet.getByTestId("not-automatic")).toContainText("No es una recomendación automática");
  await expect(sheet.getByTestId("report-footer")).toContainText(`run_id: ${RUN}`);
  await expect(sheet.getByTestId("report-footer")).toContainText("data_hash:");
  await expect(page.getByTestId("report-metadata")).toContainText(/[0-9a-f]{64}/);
  await expect(page.getByRole("link", { name: "Abrir PDF generado por el backend" })).toHaveAttribute("href", /\/v1\/reports\/.+\/pdf$/);
});

test.fixme("T-A·F el PDF real incluye anexo, resumen en inglés, hashes y referencias", async () => {
  // Requiere el generador PDF de R3 (WeasyPrint). El simulado no genera PDF.
});

test("T-A·G reproducibilidad (parte de interfaz): la corrida muestra los cinco identificadores", async ({ page }) => {
  await page.goto(`/report?runId=${RUN}`);
  const card = page.locator(".reproducibility-card");
  for (const key of ["code_version", "region_config_hash", "catalog_hash", "data_hash", "params_hash"]) {
    await expect(card).toContainText(key);
  }
  await expect(card.locator(".hash-value").nth(1)).toHaveText(/^[0-9a-f]{64}$/);
});

test.fixme("T-A·G make reproduce desde un clon limpio coincide con EXPECTED.json y corre la región alterna", async () => {
  // Depende de `make reproduce`, `data/demo/EXPECTED.json` y regions/example_alt_region.yaml (R1/R3).
});

test("T-A·H rotación multianual: ciclos, cohortes solapadas y la fecha de siembra no se presenta como rotación", async ({ page }) => {
  await page.goto(rotationsUrl);
  const catalog = page.getByTestId("strategy-catalog");
  await expect(catalog).toContainText("Rotación de dos años");
  await expect(catalog.locator("li", { hasText: "Milpa con siembra adelantada" })).toContainText("fecha de siembra");
  await expect(catalog.locator("li", { hasText: "Milpa con siembra adelantada" })).not.toContainText("rotación");
  await expect(catalog.locator("li", { hasText: "Rotación de dos años" })).toContainText("rotación");
  await expect(catalog.locator("li", { hasText: "Rotación de dos años" })).toContainText("Ciclo 2");

  const rotationCard = page.locator('[data-testid="risk-card"]', { hasText: "Rotación de dos años" });
  await expect(rotationCard).toContainText("cohortes solapadas");
  await expect(rotationCard.locator("tbody tr")).toHaveCount(2);
  await expect(rotationCard.getByTestId("peff-flag")).toBeVisible();

  await page.goto(`${calendarUrl}&heatmapView=strategy`);
  await expect(page.getByTestId("aggregation-rule")).toContainText("any/sum");
  await page.locator("select").filter({ has: page.locator('option[value="cycle"]') }).selectOption("cycle");
  await expect(page.getByTestId("heatmap")).toBeVisible();
  await expect(page.getByTestId("aggregation-rule")).toHaveCount(0);
  await expect(page.getByTestId("heatmap-legend")).toContainText("No evaluable");
});

test("T-A·I faltantes en el ranking: el criterio sale para todas y, bajo el mínimo, el resultado es insuficiente", async ({ page }) => {
  await page.goto(rotationsUrl);
  await expect(page.getByTestId("excluded-criteria")).toContainText("Alimentación");
  await expect(page.getByTestId("decision-log")).toContainText("soporte común");
  await expect(page.getByTestId("criterion-status-food")).toContainText("No evaluable");
  await expect(page.locator(".ranking-summary")).toContainText(/0[.,]75/);
  await expect(page.locator('[data-testid="ranking-table"] tbody tr')).toHaveCount(3);

  await page.getByTestId("weight-food").fill("0.9");
  await expect(page.getByTestId("ranking-panel")).toHaveAttribute("data-status", "insufficient");
  await expect(page.getByTestId("partial-table")).toBeVisible();
  await expect(page.locator('[data-testid="ranking-table"]')).toHaveCount(0);
  await expect(page.getByTestId("stability-meter")).toHaveAttribute("data-flag", "insufficient");
});

test("T-A·J privacidad (parte de interfaz): informe público sin parcela, sin coordenadas finas y borrado de parcela", async ({ page }) => {
  await page.goto(`/report?runId=${RUN}`);
  await signIn(page);
  await page.getByLabel("Privacidad del informe").selectOption("public");
  await page.getByRole("button", { name: "Solicitar informe al backend" }).click();
  await expect(page.getByTestId("report-sheet")).toContainText("Resumen ejecutivo");
  const publicText = await page.getByTestId("report-sheet").innerText();
  expect(publicText).not.toContain(PARCEL);
  await expect(page.getByTestId("public-privacy-note")).toBeVisible();

  await page.goto(zoneUrl(RUN));
  await expect(page.getByTestId("soil-table")).toBeVisible();
  const pageText = await page.locator("body").innerText();
  expect(pageText).not.toMatch(/-?\d{1,3}\.\d{4,}/); // sin coordenadas con más de tres decimales
  expect(pageText).not.toMatch(/[\w.+-]+@[\w-]+\.[\w.]+/); // sin correos

  await page.getByRole("button", { name: "Borrar esta parcela" }).click();
  await page.getByRole("button", { name: "Sí, borrar definitivamente" }).click();
  await expect(page.getByText("La parcela y sus datos fueron borrados.")).toBeVisible();
  await expect(page.getByTestId("soil-table")).toHaveCount(0);
});

test.fixme("T-A·J un segundo usuario no accede a la parcela del primero y el borrado elimina Parquet y PDFs", async () => {
  // RLS, pertenencia y borrado de archivos son responsabilidad de R3 (T-S); el simulado no tiene usuarios.
});
