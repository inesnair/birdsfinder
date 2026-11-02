import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE : chemin du site. Sur GitHub Pages c'est "/<nom-du-depot>/" (ex. "/birdsfinder/").
// En local, ou servi par FastAPI, c'est "/".
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  // onnxruntime-web charge lui-même ses fichiers .wasm (copiés dans public/ort par scripts/copy-ort.mjs)
  optimizeDeps: { exclude: ["onnxruntime-web"] },
  build: { target: "es2020", chunkSizeWarningLimit: 1200 },
});
