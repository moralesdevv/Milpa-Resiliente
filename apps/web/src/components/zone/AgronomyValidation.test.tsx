import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "../../i18n";
import type { components } from "../../api/types.gen";
import { PlantingResult, ProvisionalPlantingNotice } from "./PlantingValidation";
import { RainyOnsetView, SandboxBanner } from "./RainyOnsetSandbox";
import { StationValidationView } from "./StationValidationNotice";

type Planting = components["schemas"]["PlantingValidationResponse"];
type Onset = components["schemas"]["RainySeasonOnsetResponse"];
type Station = components["schemas"]["StationValidationResponse"];

afterEach(cleanup);

const stage = (name: string, days: number, k0: number, k1: number) => ({
  etapa_fao: name, duracion_dias: days, kc_inicio: k0, kc_fin: k1, tipo_dato: "derivado", confianza: "media-baja", supuesto_aplicado: "Derived from FAO-56 proportions",
});

const planting: Planting = {
  es_valido: false, datos_suficientes: true, alertas: ["Date is outside the configured planting window"], advertencias: ["No 15-day rainfall threshold"],
  fecha_en_ventana: false, senal_sequia: true, recomendacion: "Review", fecha_siembra: "2025-07-20", cultivo: "Maíz", variedad: "ICTA B-7", ciclo: "primera",
  precipitacion_15_dias_mm: 12.5, dias_lluvia_disponibles: 15, temperatura_media_fecha_c: 24, racha_seca_maxima_dias: 11,
  origen_senales_hidricas: "datos declarados por el usuario", fuentes_precipitacion: {}, cobertura_climatica: { desde: "2001-01-01", hasta: "2025-12-31" },
  kc_etapa_media: 1.2,
  parametros_fenologicos: { ciclo_total_dias: 120, etapas: [stage("Inicial", 19, 0.3, 0.3), stage("Desarrollo", 34, 0.3, 1.2), stage("Media", 38, 1.2, 1.2), stage("Final", 29, 1.2, 0.35)] },
  umbrales_aplicados: [{ dias_secos_consecutivos_riesgo: 10, lluvia_minima_mm_dia: 1, lluvia_minima_15_dias_mm: 20 }],
  estado_validacion: "Provisional - Pendiente validación oficial MAGA/ICTA",
  fuentes: [{ id: "FAO56", titulo: "FAO-56", institucion: "FAO", url: "https://www.fao.org/4/x0490e/x0490e0b.htm", nota: "n" }],
  supuestos: ["Kc values are FAO-56 proxies"], alcance: "Zonal", estado_reglas: "sandbox",
};

function pentads() {
  return [
    { pentada: 26, inicio: "2025-05-06", fin: "2025-05-10", precipitacion_mm: 5, dias_validos: 5, dias_totales: 5, completa: true },
    { pentada: 27, inicio: "2025-05-11", fin: "2025-05-15", precipitacion_mm: 30, dias_validos: 5, dias_totales: 5, completa: true },
    { pentada: 28, inicio: "2025-05-16", fin: "2025-05-20", precipitacion_mm: null, dias_validos: 4, dias_totales: 5, completa: false },
    { pentada: 1, inicio: "2025-01-01", fin: "2025-01-05", precipitacion_mm: 0, dias_validos: 5, dias_totales: 5, completa: true },
  ];
}

const onset: Onset = {
  fecha_estimada_inicio: "2025-05-11", metodo: "Pentad criterion", precipitacion_pentadas: pentads(), estado: "Escenario Sandbox - No usar para decisiones operativas",
  limitaciones: ["Not the official INSIVUMEH method"], fuente_precipitacion: "IMERG_FINAL_V07: 273 días", criterio: { acumulado_minimo_mm: 25, continuidad_minima_mm: 0.5 },
  anio: 2025, resultado: "detectado", entradas: { dias_con_dato: 365, primer_dia: "2025-01-01", ultimo_dia: "2025-12-31" },
  retraso_adaptacion: { dias_diferencia: 20, advertencias: ["Sowing 20 days after the onset"], conclusion: "retraso_mayor_al_umbral", mensaje: "m", nota: "Not a prediction of crop loss" },
  aviso: "x", es_metodo_oficial_insivumeh: false,
};

const station: Station = {
  estado_validacion: "Nivel C - Pendiente", mensaje: "No Camotán station data have been loaded.", metricas: null, fuente_sugerida: "INSIVUMEH - Estación Camotán",
  producto_satelital: "IMERG", carga_habilitada: false, aviso: "x", es_ejemplo_ficticio: false,
};

describe("agronomic validation UI", () => {
  it("always shows the provisional-reference notice and the sandbox banner with the required wording", async () => {
    await i18n.changeLanguage("en");
    render(<><ProvisionalPlantingNotice /><SandboxBanner /></>);
    expect(screen.getByTestId("planting-provisional")).toHaveTextContent("Planting dates and agronomic thresholds are provisional references pending official validation for Jocotán by MAGA/ICTA.");
    const banner = screen.getByTestId("sandbox-banner");
    expect(banner).toHaveTextContent("SANDBOX SIMULATION — NOT AN OPERATIONAL ALERT");
    expect(banner).toHaveTextContent("does not replace official INSIVUMEH bulletins");
  });

  it("shows the yellow window banner, the drought banner with its threshold, the Kc table and sources", async () => {
    await i18n.changeLanguage("en");
    render(<MemoryRouter><PlantingResult result={planting} /></MemoryRouter>);
    expect(screen.getByTestId("window-banner")).toHaveTextContent("not a prohibition");
    expect(screen.getByTestId("drought-banner")).toHaveTextContent("10 consecutive days with rain below 1 mm");
    const table = screen.getByTestId("phenology-table");
    expect(within(table).getByText("Mid-season")).toBeVisible();
    expect(within(table).getByText("0.30 → 1.20")).toBeVisible();
    expect(table).toHaveTextContent("120 d");
    expect(screen.getByTestId("planting-sources")).toHaveTextContent("FAO-56");
    expect(screen.getByTestId("planting-warnings")).toBeVisible();
  });

  it("does not show the window banner when the date is inside the window", async () => {
    await i18n.changeLanguage("en");
    render(<MemoryRouter><PlantingResult result={{ ...planting, fecha_en_ventana: true, senal_sequia: false, alertas: [] }} /></MemoryRouter>);
    expect(screen.queryByTestId("window-banner")).toBeNull();
    expect(screen.queryByTestId("drought-banner")).toBeNull();
  });

  it("renders the onset estimate with method, source, evaluated pentads only in April–July, gaps as 'no data' and the delay warning", async () => {
    await i18n.changeLanguage("en");
    render(<RainyOnsetView data={onset} />);
    expect(screen.getByTestId("onset-date")).toHaveTextContent("2025-05-11");
    expect(screen.getByText("Pentad criterion")).toBeVisible();
    expect(screen.getByText("IMERG_FINAL_V07: 273 días")).toBeVisible();
    const table = screen.getByTestId("pentad-table");
    expect(within(table).queryByText("2025-01-01 – 2025-01-05")).toBeNull(); // enero queda fuera de la ventana de búsqueda
    expect(within(table).getByText("no data")).toBeInTheDocument(); // un hueco nunca es 0
    expect(table).toHaveTextContent("Onset pentad");
    expect(screen.getByTestId("onset-delay")).toHaveTextContent("Sowing 20 days after the onset");
    expect(screen.getByTestId("onset-limitations")).toHaveTextContent("Not the official INSIVUMEH method");
  });

  it("says plainly when no onset was detected instead of inventing a date", async () => {
    await i18n.changeLanguage("en");
    render(<RainyOnsetView data={{ ...onset, fecha_estimada_inicio: null, resultado: "no_detectado", retraso_adaptacion: null }} />);
    expect(screen.getByTestId("onset-date")).toHaveTextContent("No onset detected");
  });

  it("keeps Level C with the required text and a disabled upload button (no fake processing)", async () => {
    await i18n.changeLanguage("en");
    render(<StationValidationView data={station} />);
    const box = screen.getByTestId("station-validation");
    expect(box).toHaveAttribute("data-level", "C");
    expect(box).toHaveTextContent("EVIDENCE LEVEL C — LOCAL VALIDATION PENDING");
    expect(box).toHaveTextContent("Satellite precipitation data have not yet been validated against the Camotán meteorological station. Historical station data are pending from INSIVUMEH.");
    const button = screen.getByRole("button", { name: "Upload Station Data (CSV)" });
    expect(button).toBeDisabled();
    expect(box).toHaveTextContent("Feature ready for future station data integration.");
    expect(box).toHaveTextContent("INSIVUMEH - Estación Camotán");
  });

  it("defaults to Level C when the request has not answered (the honest default)", async () => {
    await i18n.changeLanguage("en");
    render(<StationValidationView />);
    expect(screen.getByTestId("station-validation")).toHaveAttribute("data-level", "C");
  });

  it("shows Level B with its metrics only when the backend reports a local validation, and flags the fictitious example", async () => {
    await i18n.changeLanguage("en");
    const levelB: Station = {
      ...station, estado_validacion: "Nivel B - Validado localmente", mensaje: "Validated with 400 matching days",
      metricas: { n_comparados: 400, rmse_mm_dia: 2.1, sesgo_mm_dia: -0.3, correlacion_pearson: 0.81, periodo: { desde: "2024-01-01", hasta: "2025-02-03" }, producto_evaluado: "IMERG" },
    };
    render(<StationValidationView data={levelB} />);
    expect(screen.getByTestId("station-validation")).toHaveAttribute("data-level", "B");
    expect(screen.getByTestId("station-metrics")).toHaveTextContent("0.810");
    cleanup();
    render(<StationValidationView data={{ ...station, es_ejemplo_ficticio: true }} />);
    expect(screen.getByTestId("station-validation")).toHaveAttribute("data-level", "C");
    expect(screen.getByText(/fictitious data was found/)).toBeVisible();
  });
});
