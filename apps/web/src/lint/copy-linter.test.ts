import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { lintCopy } from "./copy-linter.ts";

test("detects the six prohibited Spanish expressions", () => {
  const text = [
    "predicción",
    "pronóstico",
    "rendimiento esperado",
    "garantiza",
    "mejor estrategia",
    "déficit real",
  ].join("; ");

  assert.deepEqual(lintCopy(text).map((finding) => finding.phrase), [
    "predicción",
    "pronóstico",
    "rendimiento esperado",
    "garantiza",
    "mejor estrategia",
    "déficit real",
  ]);
});

test("detects their English counterparts for the bilingual interface", () => {
  const text = [
    "prediction",
    "forecast",
    "expected yield",
    "guarantees",
    "best strategy",
    "actual deficit",
  ].join("; ");

  assert.deepEqual(lintCopy(text).map((finding) => finding.phrase), [
    "prediction (English)",
    "forecast (English)",
    "expected yield (English)",
    "guarantee (English)",
    "best strategy (English)",
    "real/actual deficit (English)",
  ]);
});

test("allows the explicit disclaimer contexts described by the architecture", () => {
  const text = [
    "No es una predicción.",
    "El escenario no es un pronóstico.",
    "El sistema no calcula rendimiento esperado.",
    "El resultado no garantiza un orden futuro.",
    "El producto no recomienda la mejor estrategia.",
    "El indicador no representa un déficit real del suelo.",
  ].join("\n");

  assert.deepEqual(lintCopy(text), []);
});

test("allows a coordinated negative and still catches a later positive claim", () => {
  assert.deepEqual(lintCopy("No es una predicción ni un pronóstico."), []);
  assert.deepEqual(lintCopy("It is not a prediction or a forecast."), []);

  const findings = lintCopy("No es una predicción, pero garantiza el resultado.");
  assert.deepEqual(findings.map((finding) => finding.phrase), ["garantiza"]);
});

test("reports case-insensitive matches with line and column", () => {
  const findings = lintCopy("Texto permitido.\nEl sistema GARANTIZA el resultado.");

  assert.equal(findings.length, 1);
  assert.equal(findings[0].phrase, "garantiza");
  assert.equal(findings[0].line, 2);
  assert.equal(findings[0].column, 12);
});

function collectStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(collectStrings);
  if (value && typeof value === "object") return Object.values(value).flatMap(collectStrings);
  return [];
}

for (const locale of ["es", "en"]) {
  test(`lints the ${locale} translation resource`, async () => {
    const resourcePath = fileURLToPath(new URL(`../i18n/${locale}.json`, import.meta.url));
    const resource: unknown = JSON.parse(await readFile(resourcePath, "utf8"));
    const findings = collectStrings(resource).flatMap(lintCopy);

    assert.deepEqual(findings, []);
  });
}

async function applicationCopyFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      if (["lint", "test"].includes(entry.name)) return [];
      return applicationCopyFiles(path);
    }
    if (entry.name.endsWith(".test.ts") || entry.name.endsWith(".test.tsx")) return [];
    if ([".ts", ".tsx", ".json"].some((extension) => entry.name.endsWith(extension))) return [path];
    return [];
  }));
  return nested.flat();
}

test("lints visible application source as well as translation resources", async () => {
  const sourceRoot = fileURLToPath(new URL("..", import.meta.url));
  const files = await applicationCopyFiles(sourceRoot);
  const findings = (await Promise.all(files.map(async (path) => lintCopy(await readFile(path, "utf8")))))
    .flat();
  assert.deepEqual(findings, []);
});
