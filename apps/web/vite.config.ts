import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

import { mockApiPlugin } from "./src/api/mock-api";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const useMock = env.VITE_MILPA_API_MODE === "mock";

  return {
    plugins: [react(), ...(useMock ? [mockApiPlugin()] : [])],
    server: {
      proxy: useMock ? undefined : {
        "/v1": {
          target: env.MILPA_API_PROXY || "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
