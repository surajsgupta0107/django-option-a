import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds straight into Django's static files folder (../static/react) with fixed,
// unhashed filenames so the Django template can reference them directly without
// needing a manifest.json lookup — simplest possible integration, at the cost of
// browser cache-busting on redeploys (fine for internal-tool traffic volumes; add
// hashed filenames + a manifest reader back in if that starts to matter).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The app's default API base URL is the relative path "/api" (correct once Django
    // serves the built app same-origin). Running via `npm run dev` instead (hot-reload
    // dev server on :5173) is a different origin from the Django API on :8000, so this
    // proxy forwards /api calls there — keeps the relative-path default working in both
    // modes with zero manual Settings-tab configuration needed.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "../static/react",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "index.js",
        chunkFileNames: "[name].js",
        assetFileNames: "index.[ext]",
      },
    },
  },
});
