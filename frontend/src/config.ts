/// <reference types="vite/client" />
// Réglages lus au moment du build (variables VITE_*, voir .env.example).
const env = import.meta.env;

export type InferenceMode = "onnx" | "api" | "mock";

export const config = {
  inference: ((env.VITE_INFERENCE as string) || "onnx") as InferenceMode,
  modelsBaseUrl: (env.VITE_MODELS_BASE_URL as string) || "",
  apiBaseUrl: ((env.VITE_API_BASE_URL as string) || "").replace(/\/$/, ""),
  supabaseUrl: (env.VITE_SUPABASE_URL as string) || "",
  supabaseAnonKey: (env.VITE_SUPABASE_ANON_KEY as string) || "",
  controllerName: (env.VITE_CONTROLLER_NAME as string) || "Inès (projet BirdsFinder, formation Alyra)",
  contactEmail: (env.VITE_CONTACT_EMAIL as string) || "",
  baseUrl: (env.BASE_URL as string) || "/",
  /** En dessous de cette confiance, l'appli dit qu'elle n'est pas sûre (même seuil que l'API). */
  uncertainThreshold: 0.5,
};

/** Sans Supabase configuré, les comptes et l'ornithotèque restent sur l'appareil (mode démo). */
export const demoMode = !config.supabaseUrl || !config.supabaseAnonKey;
