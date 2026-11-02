// Le "manifeste" décrit les modèles en ligne : une entrée par zone, avec ses espèces.
// Il est publié sur le Hugging Face Hub par src/publish_model.py (depuis Colab),
// ou servi par l'API FastAPI (GET /manifest) en mode "api".
import { config } from "../config";
import { mockManifest } from "./mock";

export type RegionId = "antilles" | "europe";

export interface Species {
  id: string; // nom du dossier d'entraînement, ex. "Coereba_flaveola"
  fr: string;
  sci: string;
}

export interface RegionModel {
  id: RegionId;
  label: string;
  version: string;
  architecture: string;
  file?: string; // chemin du .onnx relatif à VITE_MODELS_BASE_URL
  size_mb?: number;
  img_size: number;
  resize: number;
  mean: number[];
  std: number[];
  metrics?: { test_acc?: number; test_top3?: number; macro_f1?: number; n_test?: number };
  classes: Species[];
}

export interface Manifest {
  updated_at: string;
  regions: Partial<Record<RegionId, RegionModel>>;
}

export const REGION_ORDER: RegionId[] = ["antilles", "europe"];

export async function loadManifest(): Promise<Manifest> {
  if (config.inference === "mock") return mockManifest;
  const url =
    config.inference === "api"
      ? `${config.apiBaseUrl}/manifest`
      : `${config.modelsBaseUrl}manifest.json`;
  if (config.inference === "onnx" && !config.modelsBaseUrl) {
    throw new Error("Adresse des modèles non configurée (VITE_MODELS_BASE_URL).");
  }
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) throw new Error(`Liste des modèles introuvable (${response.status}).`);
  const manifest = (await response.json()) as Manifest;
  for (const [id, model] of Object.entries(manifest.regions)) {
    if (model) model.id = id as RegionId;
  }
  return manifest;
}

export function availableRegions(manifest: Manifest | null): RegionModel[] {
  if (!manifest) return [];
  return REGION_ORDER.map((id) => manifest.regions[id]).filter((m): m is RegionModel => !!m);
}
