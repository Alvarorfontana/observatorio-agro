import { defineConfig } from "vite";
declare const process: { env: Record<string, string | undefined> };
export default defineConfig({
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      // Mapa global de lotes Fields of the World (PMTiles, lectura por rangos)
      "/ftw": {
        target: process.env.FTW_PROXY_TARGET || "https://data.source.coop",
        changeOrigin: true,
        rewrite: (p) => process.env.FTW_PROXY_TARGET ? p : p.replace(/^\/ftw/, "/ftw/global-field-boundaries/pmtiles"),
      },
    },
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks: {
          charts: [
            "echarts/core",
            "echarts/charts",
            "echarts/components",
            "echarts/renderers",
          ],
          map: ["leaflet"],
        },
      },
    },
  },
});
