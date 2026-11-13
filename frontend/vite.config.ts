import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Optional local HTTPS for Entra SSO testing: one origin serves the SPA and proxies /api,
// so __Host- Secure session cookies work. Unset variables keep the default HTTP server.
const httpsCert = process.env.GPV_DEV_HTTPS_CERT;
const httpsKey = process.env.GPV_DEV_HTTPS_KEY;
const localHttps = httpsCert && httpsKey
  ? {
      https: { cert: readFileSync(httpsCert), key: readFileSync(httpsKey) },
      proxy: { "/api": { target: process.env.GPV_DEV_API_TARGET ?? "http://127.0.0.1:8012", changeOrigin: false } },
    }
  : {};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true, ...localHttps },
  test: { environment: "jsdom", setupFiles: ["./src/test-setup.ts"] },
});
