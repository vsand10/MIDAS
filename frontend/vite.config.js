import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // share on your Wi-Fi so you can test on your phone
    proxy: {
      // Any request to /api/... is forwarded to the FastAPI backend.
      // This is why the phone works too: it only talks to Vite.
      "/api": "http://localhost:8000",
    },
  },
});