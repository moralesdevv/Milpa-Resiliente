/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MILPA_API_MODE?: "real" | "mock";
  readonly VITE_MILPA_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
