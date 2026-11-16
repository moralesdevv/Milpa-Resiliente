/// <reference types="vite/client" />

declare module "*.geojson" {
  const geojson: {
    features: Array<{
      geometry: { coordinates: [number, number][][] };
    }>;
  };
  export default geojson;
}

interface ImportMetaEnv {
  readonly VITE_MILPA_API_MODE?: "real" | "mock";
  readonly VITE_MILPA_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
