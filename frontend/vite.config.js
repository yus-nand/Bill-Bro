import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiBaseUrl = env.VITE_API_BASE_URL || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Without this, Vite's dev server only binds to localhost — fine
      // on the Mac itself, but unreachable from a phone on the same
      // WiFi. host:true binds all interfaces so http://<your-Mac's-LAN-IP>:5173
      // works from another device too (paired with config.js inferring
      // the API host the same way, and the backend's CORS allowing LAN
      // origins — see api_app.py).
      host: true,
      // Dev-only convenience: proxy /api to the backend (Person A) so the
      // React app never needs CORS config while developing locally.
      proxy: {
        "/api": {
          target: apiBaseUrl,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
  };
});
