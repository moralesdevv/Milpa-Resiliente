import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

import { lintCopy } from "../../apps/web/src/lint/copy-linter";

export const ZONE = "00000000-0000-4000-8000-000000000001";
export const RUN = "run-synthetic-0001";
export const RUN_NO_MATRIX = "run-synthetic-nomatrix";
export const PARCEL = "parcel-synthetic-001";
export const COMBINED = encodeURIComponent("T+2_P-20_D+20_Hrh");

/** Restores the mock's in-memory state so tests do not depend on order. */
export async function resetMock(page: Page) {
  const response = await page.request.post("/v1/__mock__/reset");
  expect(response.ok()).toBe(true);
}

/** Signs in through the real sign-in form (the mock accepts any non-empty pair). */
export async function signIn(page: Page) {
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Correo electrónico").fill("tecnico@example.test");
  await page.getByLabel("Contraseña").fill("not-a-real-password");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByTestId("session-control")).toContainText("Sesión iniciada");
}

/** Fails if visible text makes a prohibited claim (forecast, expected yield, real deficit…). */
export async function expectNoProhibitedClaims(page: Page) {
  const text = await page.locator("body").innerText();
  expect(lintCopy(text)).toEqual([]);
}
