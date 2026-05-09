import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite + React. The dev server proxies ``/v1`` to the FastAPI backend on
// :8000 so the SPA can call relative URLs in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": "http://localhost:8000",
    },
  },
  test: {
    globals: true,
    environment: "node",
  },
});
