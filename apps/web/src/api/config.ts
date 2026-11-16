export const apiMode = import.meta.env.VITE_MILPA_API_MODE === "mock" ? "mock" : "real";
export const apiBaseUrl = import.meta.env.VITE_MILPA_API_BASE_URL?.trim() ?? "";
