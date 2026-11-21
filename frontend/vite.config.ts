import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: /api → backend FastAPI na :8000 (bez CORS w przeglądarce)
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
