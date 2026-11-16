import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, assertResponse } from "./client";
import { toDekadChart, toHeatmap, toRankResponse, toScenarioTags, toSummaryPage } from "./r2-adapters";
import { toQualityView, toSoilStatusView, toZoneView, uploadFromOk, uploadFromProblem } from "./adapters";
import type { UploadView } from "./adapters";
import type { components } from "./types.gen";
import i18n from "../i18n";
import { apiBaseUrl } from "./config";
import { getSession } from "./session";

export type SoilGridsSummary = {
  status: string;
  status_detail: string | null;
  depth: string;
  note: string;
  points?: number;
  properties: Record<string, { value: number | null; unit: string; valid_points: number }>;
};

export function useJocotanSoilGrids(enabled: boolean) {
  return useQuery({
    queryKey: ["soilgrids", "jocotan"],
    enabled,
    queryFn: async (): Promise<SoilGridsSummary> => {
      const response = await fetch(
        `${import.meta.env.BASE_URL}data/soilgrids/jocotan_promedio.json`,
      );
      if (!response.ok) throw new Error("SoilGrids summary is not available.");
      const raw = (await response.json()) as SoilGridsSummary & { points_inside_polygon?: number };
      return { ...raw, points: raw.points_inside_polygon };
    },
  });
}

export function useZones() {
  return useQuery({
    queryKey: ["zones"],
    queryFn: async () => {
      const result = await api.GET("/v1/zones");
      assertResponse(result.response, result.error);
      return result.data?.items ?? [];
    },
  });
}

export function useZone(zoneId: string | null) {
  return useQuery({
    queryKey: ["zone", zoneId],
    enabled: Boolean(zoneId),
    queryFn: async () => {
      if (!zoneId) throw new Error("A zone must be selected before loading its details.");
      const result = await api.GET("/v1/zones/{id}", { params: { path: { id: zoneId } } });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The zone response was empty.");
      return toZoneView(result.data);
    },
  });
}

export function useZoneDataQuality(zoneId: string | null) {
  return useQuery({
    queryKey: ["zone-data-quality", zoneId],
    enabled: Boolean(zoneId),
    queryFn: async () => {
      if (!zoneId) throw new Error("A zone must be selected before loading its data quality.");
      const result = await api.GET("/v1/zones/{id}/data-quality", { params: { path: { id: zoneId } } });
      assertResponse(result.response, result.error);
      return result.data ? toQualityView(result.data) : undefined;
    },
  });
}

export function useParcelSoil(parcelId: string | null) {
  return useQuery({
    queryKey: ["parcel-soil", parcelId],
    enabled: Boolean(parcelId),
    queryFn: async () => {
      if (!parcelId) throw new Error("A parcel must be selected before loading soil properties.");
      const result = await api.GET("/v1/parcels/{id}/soil", { params: { path: { id: parcelId } } });
      assertResponse(result.response, result.error);
      return (result.data ?? []).map(toSoilStatusView);
    },
  });
}

export function usePlantingValidation(parcelId: string | null) {
  return useMutation({
    mutationFn: async (request: components["schemas"]["PlantingValidationRequest"]) => {
      if (!parcelId) throw new Error("A parcel must be selected before validating planting.");
      const result = await api.POST("/v1/parcels/{id}/planting-validation", {
        params: { path: { id: parcelId } },
        body: request,
      });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The planting validation response was empty.");
      return result.data;
    },
  });
}

export function useZonePlantingValidation(zoneId: string | null) {
  return useMutation({
    mutationFn: async (request: components["schemas"]["PlantingValidationRequest"]) => {
      if (!zoneId) throw new Error("A Jocotán zone must be selected before checking planting.");
      const result = await api.GET("/v1/zones/{id}/planting-validation", {
        params: {
          path: { id: zoneId },
          query: request,
        },
      });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The planting validation response was empty.");
      return result.data;
    },
  });
}

export function useStrategyVersion(strategyId: string, version: number | null | undefined) {
  return useQuery({
    queryKey: ["strategy-version", strategyId, version],
    enabled: version != null,
    queryFn: async () => {
      if (version == null) throw new Error("The strategy has no published version.");
      const result = await api.GET("/v1/catalog/strategies/{id}/versions/{v}", { params: { path: { id: strategyId, v: version } } });
      assertResponse(result.response, result.error);
      return result.data;
    },
  });
}

export function useRunScenarios(runId: string | null) {
  return useQuery({
    queryKey: ["run-scenarios", runId],
    enabled: Boolean(runId),
    queryFn: async () => {
      if (!runId) throw new Error("A run must be selected before loading scenarios.");
      const result = await api.GET("/v1/runs/{id}/scenarios", { params: { path: { id: runId } } });
      assertResponse(result.response, result.error);
      return toScenarioTags(result.data ?? []);
    },
  });
}

export function useClimateHistory(runId: string | null) {
  return useQuery({
    queryKey: ["climate-history", runId],
    enabled: Boolean(runId),
    queryFn: async () => {
      if (!runId) throw new Error("A run must be selected before loading climate history.");
      const result = await api.GET("/v1/runs/{id}/climate-history", { params: { path: { id: runId } } });
      assertResponse(result.response, result.error);
      return result.data;
    },
  });
}

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: ["run", runId],
    enabled: Boolean(runId),
    queryFn: async () => {
      if (!runId) throw new Error("A run identifier is required.");
      const result = await api.GET("/v1/runs/{id}", { params: { path: { id: runId } } });
      assertResponse(result.response, result.error);
      return result.data;
    },
  });
}

export function useRunSummary(runId: string | null, scenario: string | null, adaptation: components["schemas"]["AdaptationMode"]) {
  return useQuery({
    queryKey: ["run-summary", runId, scenario, adaptation],
    enabled: Boolean(runId && scenario),
    queryFn: async () => {
      if (!runId || !scenario) throw new Error("A run and computed scenario are required.");
      const result = await api.GET("/v1/runs/{id}/summary", {
        params: { path: { id: runId }, query: { scenario, adaptation } },
      });
      assertResponse(result.response, result.error);
      return result.data ? toSummaryPage(result.data) : undefined;
    },
  });
}

export function useHeatmap(runId: string | null, options: {
  view: components["schemas"]["HeatmapDTO"]["view"];
  strategy: string | null;
  cycle?: number;
  variety?: string;
  scenario: string | null;
  adaptation: components["schemas"]["AdaptationMode"];
}) {
  return useQuery({
    queryKey: ["heatmap", runId, options],
    enabled: Boolean(runId && options.strategy && options.scenario),
    queryFn: async () => {
      if (!runId || !options.strategy || !options.scenario) throw new Error("Run, strategy and scenario are required.");
      const result = await api.GET("/v1/runs/{id}/heatmap", {
        params: {
          path: { id: runId },
          query: {
            view: options.view,
            strategy: options.strategy,
            cycle: options.cycle,
            variety: options.variety,
            scenario: options.scenario,
            adaptation: options.adaptation,
          },
        },
      });
      assertResponse(result.response, result.error);
      return result.data ? toHeatmap(result.data, options.view, options.strategy) : null;
    },
  });
}

export function useDekadChart(runId: string | null, options: {
  strategy: string | null;
  cohortYear?: number;
  cycle?: number;
  plantDate?: string;
  scenario: string | null;
}) {
  return useQuery({
    queryKey: ["dekad-chart", runId, options],
    enabled: Boolean(runId && options.strategy && options.scenario && options.cohortYear && options.cycle !== undefined && options.plantDate),
    queryFn: async () => {
      if (!runId || !options.strategy || !options.scenario || options.cohortYear === undefined || options.cycle === undefined || !options.plantDate) {
        throw new Error("Run, strategy, cohort, cycle, planting date and scenario are required.");
      }
      const result = await api.GET("/v1/runs/{id}/dekad-chart", {
        params: { path: { id: runId }, query: {
          strategy: options.strategy,
          cohort_year: options.cohortYear,
          cycle: options.cycle,
          // The heat-map axis is month-day; the endpoint wants the calendar date of the cohort's planting.
          plant_date: /^\d{2}-\d{2}$/.test(options.plantDate) ? `${options.cohortYear}-${options.plantDate}` : options.plantDate,
          scenario: options.scenario,
        } },
      });
      assertResponse(result.response, result.error);
      if (!result.data) return null;
      const raw = result.data as { provenance_info?: components["schemas"]["ProvenanceInfo"] };
      return toDekadChart(result.data, raw.provenance_info);
    },
  });
}

/** Ranking recalculated by the backend from persisted results (synchronous endpoint). */
export function useRank(runId: string | null, request: components["schemas"]["RankRequest"] | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["rank", runId, request],
    enabled: Boolean(runId && request),
    retry: false,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      if (!runId || !request) throw new Error("A run and a ranking request are required.");
      const result = await api.POST("/v1/runs/{id}/rank", { params: { path: { id: runId } }, body: request });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The ranking response was empty.");
      const names: Record<string, string> = {};
      for (const [, page] of queryClient.getQueriesData<components["schemas"]["PageStrategyRiskDTO"]>({ queryKey: ["run-summary", runId] })) {
        for (const item of page?.items ?? []) names[item.strategy_version_id] = item.name;
      }
      return toRankResponse(result.data, names);
    },
  });
}

export function useSoilVoi(runId: string | null) {
  return useMutation({
    mutationFn: async () => {
      if (!runId) throw new Error("A run must be selected before checking soil information value.");
      const result = await api.POST("/v1/runs/{id}/soil-voi", { params: { path: { id: runId } } });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The soil information response was empty.");
      return result.data;
    },
  });
}

export function useCreateReport() {
  return useMutation({
    mutationFn: async (request: components["schemas"]["ReportCreate"]) => {
      const result = await api.POST("/v1/reports", { body: request });
      assertResponse(result.response, result.error);
      return result.data;
    },
  });
}

export function useReport(reportId: string | null) {
  return useQuery({
    queryKey: ["report", reportId],
    enabled: Boolean(reportId),
    queryFn: async () => {
      if (!reportId) throw new Error("A report identifier is required.");
      const result = await api.GET("/v1/reports/{id}", { params: { path: { id: reportId } } });
      assertResponse(result.response, result.error);
      return result.data;
    },
  });
}

export function useParcel(parcelId: string | null) {
  return useQuery({
    queryKey: ["parcel", parcelId],
    enabled: Boolean(parcelId),
    retry: false,
    queryFn: async () => {
      if (!parcelId) throw new Error("A parcel must be selected.");
      const result = await api.GET("/v1/parcels/{id}", { params: { path: { id: parcelId } } });
      assertResponse(result.response, result.error);
      return result.data;
    },
  });
}

export function useStrategyCatalog() {
  return useQuery({
    queryKey: ["strategy-catalog"],
    queryFn: async () => {
      const result = await api.GET("/v1/catalog/strategies");
      assertResponse(result.response, result.error);
      return result.data?.items ?? [];
    },
  });
}

const finishedStates: components["schemas"]["JobStatus"][] = ["ok", "failed", "cancelled"];

/** Polls a background job until it reaches a final state. */
export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    enabled: Boolean(jobId),
    gcTime: 0,
    staleTime: 0,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && finishedStates.includes(status) ? false : 600;
    },
    queryFn: async () => {
      if (!jobId) throw new Error("A job identifier is required.");
      const result = await api.GET("/v1/jobs/{id}", { params: { path: { id: jobId } } });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The job response was empty.");
      return result.data;
    },
  });
}

export function useRunScenariosJob(runId: string | null) {
  return useMutation({
    mutationFn: async (request: components["schemas"]["ScenariosCreate"]) => {
      if (!runId) throw new Error("A run must be selected before launching scenarios.");
      const result = await api.POST("/v1/runs/{id}/scenarios", { params: { path: { id: runId } }, body: request });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The scenario job response was empty.");
      return result.data;
    },
  });
}

export function useUploadSoilSamples(parcelId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<UploadView> => {
      if (!parcelId) throw new Error("A parcel must be selected before uploading soil data.");
      // R3 recibe el archivo tal cual (text/csv, UTF-8): contrato POST /v1/parcels/{id}/soil-samples.
      const session = getSession();
      const response = await fetch(`${apiBaseUrl}/v1/parcels/${encodeURIComponent(parcelId)}/soil-samples`, {
        method: "POST",
        headers: { "Content-Type": "text/csv", ...(session ? { Authorization: `Bearer ${session.token}` } : {}) },
        body: await file.text(),
      });
      const payload: unknown = await response.json().catch(() => undefined);
      if (response.ok) return uploadFromOk(payload as components["schemas"]["SoilCsvResult"]);
      const problem = payload as components["schemas"]["ProblemDetail"] | undefined;
      // 422 CSV_VALIDATION_FAILED: errores por fila; se muestran, no se tratan como fallo de red.
      if (response.status === 422 && problem?.code === "CSV_VALIDATION_FAILED") return uploadFromProblem(problem);
      assertResponse(response, payload);
      throw new Error("The upload failed.");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parcel-soil", parcelId] }),
  });
}

export function useDeclareSoilProperty(parcelId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ property, body }: { property: string; body: components["schemas"]["SoilDeclarationIn"] }) => {
      if (!parcelId) throw new Error("A parcel must be selected before declaring soil data.");
      const result = await api.PUT("/v1/parcels/{id}/soil-declarations/{property}", { params: { path: { id: parcelId, property } }, body });
      assertResponse(result.response, result.error);
      return result.data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["parcel-soil", parcelId] }),
  });
}

export function useDeleteParcel(parcelId: string | null) {
  return useMutation({
    mutationFn: async () => {
      if (!parcelId) throw new Error("A parcel must be selected before deleting it.");
      const result = await api.DELETE("/v1/parcels/{id}", { params: { path: { id: parcelId } } });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The deletion job response was empty.");
      return result.data;
    },
  });
}

/** Language of the messages the backend generates (the product UI is English; Spanish stays available). */
function uiLanguage(): "es" | "en" {
  return i18n.language.startsWith("es") ? "es" : "en";
}

export function usePlantingOptions(zoneId: string | null) {
  return useQuery({
    queryKey: ["planting-options", zoneId],
    enabled: Boolean(zoneId),
    staleTime: 5 * 60_000,
    queryFn: async () => {
      if (!zoneId) throw new Error("A zone is required.");
      const result = await api.GET("/v1/zones/{id}/planting-options", { params: { path: { id: zoneId } } });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The planting options response was empty.");
      return result.data;
    },
  });
}

export function useRainyOnset(zoneId: string | null, year: number | null, plantingDate: string | null) {
  return useQuery({
    queryKey: ["rainy-onset", zoneId, year, plantingDate],
    enabled: Boolean(zoneId) && year != null,
    queryFn: async () => {
      if (!zoneId || year == null) throw new Error("A zone and a year are required.");
      const result = await api.GET("/v1/zones/{id}/rainy-season-onset", {
        params: { path: { id: zoneId }, query: { anio: year, idioma: uiLanguage(), ...(plantingDate ? { fecha_siembra: plantingDate } : {}) } },
      });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The rainy-season onset response was empty.");
      return result.data;
    },
  });
}

export function useStationValidation(zoneId: string | null) {
  return useQuery({
    queryKey: ["station-validation", zoneId],
    enabled: Boolean(zoneId),
    queryFn: async () => {
      if (!zoneId) throw new Error("A zone is required.");
      const result = await api.GET("/v1/zones/{id}/station-validation", { params: { path: { id: zoneId }, query: { idioma: uiLanguage() } } });
      assertResponse(result.response, result.error);
      if (!result.data) throw new Error("The station validation response was empty.");
      return result.data;
    },
  });
}
