import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { pickLanguage, readTable, ReportSectionBlock } from "./ReportSection";

const SECTION = {
  title_es: "Riesgo por estrategia",
  title_en: "Risk by strategy",
  body_es: "Indicador de exposición climática.",
  body_en: "Climate-exposure indicator.",
  items: ["punto en español"],
  items_en: ["point in English"],
  table: {
    caption_es: "Frecuencia (%)",
    caption_en: "Frequency (%)",
    headers: ["Estrategia / Strategy", "Valor / Value"],
    rows: [["Maíz / Maize", "4.0 %"], ["Sorgo / Sorghum", "n/d"]],
    weights: [3, 1],
  },
};

describe("report section", () => {
  afterEach(cleanup);

  it("renders the Spanish half of a bilingual report with its table and units", () => {
    render(<ReportSectionBlock section={SECTION} english={false} fallbackTitle="?" />);
    expect(screen.getByRole("heading", { name: "Riesgo por estrategia" })).toBeVisible();
    expect(screen.getByText("punto en español")).toBeVisible();
    const table = screen.getByTestId("report-table");
    expect(within(table).getByRole("columnheader", { name: "Estrategia" })).toBeVisible();
    expect(within(table).getByRole("rowheader", { name: "Maíz" })).toBeVisible();
    expect(within(table).getByText("4.0 %")).toBeVisible();
    expect(within(table).getByText("n/d")).toBeVisible(); // missing figure is stated, never shown as 0
    expect(screen.getByText("Frecuencia (%)")).toBeVisible();
  });

  it("renders the English half when the interface is English", () => {
    render(<ReportSectionBlock section={SECTION} english fallbackTitle="?" />);
    expect(screen.getByRole("heading", { name: "Risk by strategy" })).toBeVisible();
    expect(screen.getByText("point in English")).toBeVisible();
    expect(within(screen.getByTestId("report-table")).getByRole("columnheader", { name: "Strategy" })).toBeVisible();
    expect(screen.getByText("Frequency (%)")).toBeVisible();
  });

  it("falls back to the Spanish items when the English list is absent and ignores malformed tables", () => {
    const withoutEnglishItems: Record<string, unknown> = { ...SECTION };
    delete withoutEnglishItems.items_en;
    render(<ReportSectionBlock section={{ ...withoutEnglishItems, table: { headers: ["a", "b"], rows: [["solo-una"]] } }} english fallbackTitle="?" />);
    expect(screen.getByText("punto en español")).toBeVisible();
    expect(screen.queryByText("solo-una")).toBeNull(); // a ragged row is dropped, not guessed
  });

  it("uses the fallback title when the section has none", () => {
    render(<ReportSectionBlock section={{ body_es: "texto" }} english={false} fallbackTitle="Sección sin título" />);
    expect(screen.getByRole("heading", { name: "Sección sin título" })).toBeVisible();
  });

  it("parses weights only when valid and keeps single-language values untouched", () => {
    expect(readTable(SECTION, false)?.weights).toEqual([3, 1]);
    expect(readTable({ table: { headers: ["a"], rows: [], weights: [0] } }, false)?.weights).toBeNull();
    expect(readTable({}, false)).toBeNull();
    expect(pickLanguage("solo español", true)).toBe("solo español");
    expect(pickLanguage("A / B / C", true)).toBe("A / B / C");
  });
});
