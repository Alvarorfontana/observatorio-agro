import { defineConfig } from "vite";
export default defineConfig({
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
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
