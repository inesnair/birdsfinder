// Reconnaissance d'une photo, selon le mode configuré :
//  - onnx : le modèle tourne DANS le navigateur (la photo ne quitte pas l'appareil)
//  - api  : la photo est envoyée à l'API FastAPI (démo Colab / local)
//  - mock : scores inventés, pour développer l'interface
import { config } from "../config";
import type { RegionModel, Species } from "./manifest";
import { imageToTensorData } from "./image";
import { mockScores } from "./mock";

export interface Prediction {
  species: Species;
  confidence: number;
}

export type Progress = { phase: "download"; loaded: number; total: number } | { phase: "analyse" };

type OrtModule = typeof import("onnxruntime-web");
type Session = import("onnxruntime-web").InferenceSession;

let ortPromise: Promise<OrtModule> | null = null;
const sessions = new Map<string, Promise<Session>>();
const MODEL_CACHE = "birdsfinder-models-v1";

export async function classify(
  model: RegionModel,
  img: HTMLImageElement,
  file: Blob,
  onProgress?: (p: Progress) => void,
  topK = 3,
): Promise<Prediction[]> {
  if (config.inference === "api") return classifyWithApi(model, file, topK);
  let probs: number[];
  if (config.inference === "mock") {
    onProgress?.({ phase: "analyse" });
    await new Promise((r) => setTimeout(r, 400));
    probs = await mockScores(file, model.classes.length);
  } else {
    const session = await getSession(model, onProgress);
    onProgress?.({ phase: "analyse" });
    const ort = await loadOrt();
    const data = imageToTensorData(img, model.resize, model.img_size, model.mean, model.std);
    const input = new ort.Tensor("float32", data, [1, 3, model.img_size, model.img_size]);
    const output = await session.run({ [session.inputNames[0]]: input });
    probs = softmax(Array.from(output[session.outputNames[0]].data as Float32Array));
  }
  return topPredictions(probs, model.classes, topK);
}

/** Le modèle est-il déjà téléchargé sur cet appareil ? (pour annoncer un téléchargement) */
export async function isModelCached(model: RegionModel): Promise<boolean> {
  if (config.inference !== "onnx" || !model.file) return true;
  try {
    const cache = await caches.open(MODEL_CACHE);
    return !!(await cache.match(modelUrl(model)));
  } catch {
    return false;
  }
}

function modelUrl(model: RegionModel): string {
  return `${config.modelsBaseUrl}${model.file}`;
}

function loadOrt(): Promise<OrtModule> {
  if (!ortPromise) {
    ortPromise = import("onnxruntime-web").then((ort) => {
      ort.env.wasm.wasmPaths = `${config.baseUrl}ort/`; // fichiers servis par le site lui-même
      ort.env.wasm.numThreads = 1; // GitHub Pages ne permet pas le multi-thread WebAssembly
      return ort;
    });
  }
  return ortPromise;
}

function getSession(model: RegionModel, onProgress?: (p: Progress) => void): Promise<Session> {
  if (!model.file) return Promise.reject(new Error("Ce modèle n'a pas de fichier ONNX publié."));
  const key = modelUrl(model);
  let session = sessions.get(key);
  if (!session) {
    session = (async () => {
      const bytes = await downloadModel(key, onProgress);
      const ort = await loadOrt();
      return ort.InferenceSession.create(bytes, { executionProviders: ["wasm"] });
    })();
    session.catch(() => sessions.delete(key));
    sessions.set(key, session);
  }
  return session;
}

/** Télécharge le modèle une seule fois puis le garde en cache (l'URL contient la version). */
async function downloadModel(url: string, onProgress?: (p: Progress) => void): Promise<Uint8Array> {
  let cache: Cache | null = null;
  try {
    cache = await caches.open(MODEL_CACHE);
    const hit = await cache.match(url);
    if (hit) return new Uint8Array(await hit.arrayBuffer());
  } catch {
    cache = null; // Cache API indisponible : on télécharge à chaque session
  }
  const response = await fetch(url);
  if (!response.ok || !response.body) throw new Error(`Téléchargement du modèle impossible (${response.status}).`);
  const total = Number(response.headers.get("content-length")) || 0;
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let loaded = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    loaded += value.length;
    onProgress?.({ phase: "download", loaded, total });
  }
  const bytes = new Uint8Array(loaded);
  let offset = 0;
  for (const c of chunks) {
    bytes.set(c, offset);
    offset += c.length;
  }
  if (cache) {
    try {
      await cache.put(url, new Response(bytes, { headers: { "content-type": "application/octet-stream" } }));
    } catch {
      /* cache plein : tant pis */
    }
  }
  return bytes;
}

async function classifyWithApi(model: RegionModel, file: Blob, topK: number): Promise<Prediction[]> {
  const form = new FormData();
  form.append("file", file, "photo.jpg");
  const response = await fetch(`${config.apiBaseUrl}/predict/image?region=${encodeURIComponent(model.id)}`, {
    method: "POST",
    body: form,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `L'API a répondu ${response.status}.`);
  const byId = new Map(model.classes.map((s) => [s.id, s]));
  return (body.predictions as { species_id: string; name_fr: string; scientific_name?: string; confidence: number }[])
    .slice(0, topK)
    .map((p) => ({
      species: byId.get(p.species_id) ?? { id: p.species_id, fr: p.name_fr, sci: p.scientific_name ?? "" },
      confidence: p.confidence,
    }));
}

export function softmax(logits: number[]): number[] {
  const max = Math.max(...logits);
  const exps = logits.map((x) => Math.exp(x - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map((e) => e / sum);
}

export function topPredictions(probs: number[], classes: Species[], k: number): Prediction[] {
  return probs
    .map((confidence, i) => ({ species: classes[i], confidence }))
    .filter((p) => p.species)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, k);
}
