import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import i18n from "../i18n";
import * as fx from "../api/mock-fixture";
import { deepScenarioPlain, scenarioToWire } from "../api/mock-wire";

/** Fixture del borrador de R4 → forma en el cable (ScenarioTag con números simples, §15). */
const wire = (value: unknown) => deepScenarioPlain<never>(value);
import { Heatmap } from "./charts/Heatmap";
import { PositionInversions } from "./charts/PositionInversions";
import { StabilityMeter } from "./charts/StabilityMeter";
import { EvidenceBadge, Indicator } from "./indicator/Indicator";
import { ScenarioBadge } from "./scenario/ScenarioComponents";

const weights = { water: 0.25, soil: 0.25, food: 0.25, income: 0.25 };

describe("componentes de presentación", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("es");
  });

  it("Indicator muestra valor, unidad, nivel de evidencia y acceso a la procedencia", () => {
    const indicator = wire(fx.ind("t.demo", "Severidad", "Severity", 12.345, "mm", "exposure"));
    render(<Indicator indicator={indicator} />);
    expect(screen.getByText(/12,35|12\.35/)).toBeVisible();
    expect(screen.getByText("Evidencia C")).toBeVisible();
    expect(screen.getByText("Ver procedencia")).toBeVisible();
    expect(screen.getByText(fx.FIXTURE_NOTE, { selector: ".indicator__reason" })).toBeVisible();
  });

  it("Indicator nunca convierte un valor nulo en cero", () => {
    const { container } = render(<Indicator indicator={wire(fx.ind("t.null", "Cobertura", "Coverage", null, "mm"))} />);
    const value = container.querySelector(".indicator__value");
    expect(value).toHaveTextContent("No disponible");
    expect(value?.textContent).not.toMatch(/^0/);
  });

  it("EvidenceBadge se traduce al inglés sin texto fijo", async () => {
    await i18n.changeLanguage("en");
    render(<EvidenceBadge evidence="B" provenance="satelital" />);
    expect(screen.getByText("Evidence B")).toBeVisible();
  });

  it("ScenarioBadge muestra rótulo, parámetros, humedad y lectura de adaptación", () => {
    render(<ScenarioBadge scenario={scenarioToWire(fx.scenarioTag(fx.COMBINED, "onset_rule")) as never} />);
    const badge = screen.getByLabelText("Escenario sintético aplicado");
    expect(within(badge).getByText("Escenario sintético")).toBeVisible();
    expect(badge).toHaveTextContent("Humedad relativa constante");
    expect(badge).toHaveTextContent("Regla de inicio de lluvias");
    expect(badge).toHaveTextContent("20");
  });

  it("Heatmap diferencia los cuatro estados con texto y marca, no solo con color, y muestra la regla any/sum", () => {
    const raw = fx.heatmap("strategy", fx.STRATEGY_REF, null, fx.BASE, "none");
    const data = wire(raw);
    const { container } = render(<Heatmap data={data} />);
    const legend = screen.getByTestId("heatmap-legend");
    for (const label of ["Crítico", "No crítico", "Información insuficiente", "No evaluable"]) expect(legend).toHaveTextContent(label);
    const states = new Set([...container.querySelectorAll("td[data-state]")].map((cell) => cell.getAttribute("data-state")));
    expect(states).toEqual(new Set(["critical", "non_critical", "insufficient_data", "not_evaluable"]));
    for (const cell of container.querySelectorAll("td[data-state]")) expect((cell.textContent ?? "").trim().length).toBeGreaterThan(0);
    expect(screen.getByTestId("aggregation-rule")).toHaveTextContent("any/sum");
    expect(container.querySelectorAll("tfoot td").length).toBe(raw.plant_md.length);
  });

  it("StabilityMeter acepta solo los cuatro estados y repite siempre la interpretación", () => {
    const stability = wire(fx.rank(fx.BASE, "none", weights).stability);
    render(<StabilityMeter stability={stability} />);
    expect(screen.getByTestId("stability-note")).toHaveTextContent("Mide sensibilidad a los pesos, no la probabilidad de ser la mejor");
    expect(["stable", "moderate", "unstable", "insufficient"]).toContain(screen.getByTestId("stability-meter").getAttribute("data-flag"));
  });

  it("PositionInversions solo compara posiciones y marca los cambios", () => {
    const base = wire(fx.rank(fx.BASE, "none", weights));
    const scenario = wire(fx.rank(fx.COMBINED, "none", weights));
    render(<PositionInversions base={base} selected={scenario} />);
    expect(screen.getByTestId("inversions")).toHaveTextContent("El orden cambia respecto de BASE");
  });

  it("PositionInversions no compara si falta uno de los rankings", () => {
    render(<PositionInversions base={null} selected={wire(fx.rank(fx.BASE, "none", weights))} />);
    expect(screen.getByText("Se necesita el ranking de BASE y el del escenario elegido.")).toBeVisible();
  });
});
