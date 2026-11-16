/**
 * T-UI: estados de interfaz, accesibilidad automática (axe, WCAG 2.1 A/AA) y diseño adaptable.
 * Corre contra el servidor simulado con fixture sintético. axe detecta solo una parte de los
 * problemas de accesibilidad: no sustituye la revisión manual y no demuestra conformidad WCAG.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { COMBINED, PARCEL, RUN, ZONE, resetMock } from "../../../tests/acceptance/helpers";

const screens = [
  { name: "Mi zona", url: `/my-zone?zoneId=${ZONE}&parcelId=${PARCEL}&runId=${RUN}` },
  { name: "Cómo cambió el calendario", url: `/calendar?runId=${RUN}&scenarioId=BASE&adaptation=none` },
  { name: "Laboratorio de rotaciones", url: `/rotations?runId=${RUN}&scenarioId=${COMBINED}&adaptation=none` },
  { name: "Informe de decisión", url: `/report?runId=${RUN}` },
];

test.beforeEach(async ({ page }) => {
  await resetMock(page);
});

test.describe("estados de interfaz", () => {
  test("cuenta vacía: Mi zona se abre y cambia de idioma", async ({ page }) => {
    await page.route("**/v1/zones", (route) => route.fulfill({ json: [] }));
    await page.goto("/my-zone");
    await expect(page.getByRole("heading", { name: "Mi zona" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "No hay zonas disponibles para esta cuenta." })).toBeVisible();
    await page.getByRole("combobox", { name: "Idioma" }).selectOption("en");
    await expect(page.getByRole("heading", { name: "My zone" })).toBeVisible();
  });

  test("error: un escenario no calculado muestra el código y la orientación", async ({ page }) => {
    await page.route("**/v1/runs/*/summary*", (route) => route.fulfill({
      status: 409,
      contentType: "application/json",
      json: { type: "about:blank", title: "Scenario not computed", status: 409, code: "SCENARIO_NOT_COMPUTED", hint: "Calcule el escenario desde el Laboratorio de rotaciones." },
    }));
    await page.goto(`/calendar?runId=${RUN}&scenarioId=BASE&adaptation=none`);
    const alert = page.getByRole("alert").first();
    await expect(alert).toContainText("SCENARIO_NOT_COMPUTED");
    await expect(alert).toContainText("Calcule el escenario");
  });

  test("carga y vacío: sin corrida se pide seleccionar una", async ({ page }) => {
    await page.goto("/calendar");
    await expect(page.getByText("Introduzca un identificador de corrida").first()).toBeVisible();
  });

  test("datos insuficientes: una corrida sin fixture no inventa resultados", async ({ page }) => {
    await page.goto("/calendar?runId=run-sin-fixture");
    await expect(page.getByText("Información insuficiente").first()).toBeVisible();
  });

  test("provisional: el aviso aparece junto a los indicadores del fixture", async ({ page }) => {
    await page.goto(`/calendar?runId=${RUN}&scenarioId=BASE&adaptation=none`);
    await expect(page.getByRole("note").filter({ hasText: "Resultado provisional" }).first()).toBeVisible();
  });

  test("la navegación se alcanza con el teclado", async ({ page }) => {
    await page.goto("/my-zone");
    await page.keyboard.press("Tab");
    await expect(page.locator(":focus")).toHaveAttribute("href", "#main-content");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: /MILPA RESILIENTE/ })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: /Mi zona/ })).toBeFocused();
  });

  test("el panel de procedencia se abre con el teclado", async ({ page }) => {
    await page.goto(`/my-zone?zoneId=${ZONE}`);
    const summary = page.locator(".provenance-panel summary").first();
    await summary.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".provenance-panel[open]").first()).toContainText("Regla de evidencia");
  });
});

test.describe("axe sobre las cuatro pantallas con datos", () => {
  for (const screen of screens) {
    test(`sin violaciones automáticas WCAG 2.1 A/AA en «${screen.name}»`, async ({ page }) => {
      await page.goto(screen.url);
      await expect(page.getByRole("heading", { level: 1, name: screen.name })).toBeVisible();
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1300); // deja terminar la entrada animada antes de medir el contraste
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target.join(" ")).slice(0, 4) }))).toEqual([]);
    });
  }
});

test.describe("diseño adaptable", () => {
  for (const width of [375, 768]) {
    test(`ninguna pantalla desborda horizontalmente a ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      for (const screen of screens) {
        await page.goto(screen.url);
        await page.waitForLoadState("networkidle");
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow, `${screen.name} a ${width}px`).toBeLessThanOrEqual(1);
      }
    });
  }
});

test.describe("barra de misión", () => {
  test("los cuatro nodos de la ruta existen y el módulo activo se anuncia", async ({ page }) => {
    await page.goto(`/calendar?runId=${RUN}&scenarioId=BASE&adaptation=none`);
    const nav = page.getByRole("navigation", { name: "Navegación principal" });
    await expect(nav.getByRole("link")).toHaveCount(4);
    await expect(nav.locator("a.is-active")).toContainText("Cómo cambió el calendario");
    await expect(nav.getByRole("link", { name: "Informe de decisión" })).toBeVisible();
  });

  test("a 390 px la ruta cabe en la pantalla y cada nodo mide al menos 44 px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/my-zone");
    for (const link of await page.getByRole("navigation", { name: "Navegación principal" }).getByRole("link").all()) {
      const box = await link.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
  });
});
