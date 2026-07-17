import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  // Caminhos relativos: o build funciona servido em qualquer prefixo
  // (o Core monta o dashboard em /app).
  base: "./",
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8600",
      "/ws": {
        target: "ws://127.0.0.1:8600",
        ws: true,
      },
    },
  },
});
