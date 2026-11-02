// Données factices, utilisées seulement avec VITE_INFERENCE=mock (développement de l'interface).
// Les prédictions y sont inventées : ne jamais utiliser ce mode pour une démonstration du modèle.
import type { Manifest, Species } from "./manifest";

const sp = (sci: string, fr: string): Species => ({ id: sci.replace(/[^A-Za-z0-9]+/g, "_"), fr, sci });

const common = {
  version: "maquette",
  architecture: "convnext_tiny",
  img_size: 224,
  resize: 256,
  mean: [0.485, 0.456, 0.406],
  std: [0.229, 0.224, 0.225],
};

export const mockManifest: Manifest = {
  updated_at: "2026-11-02T20:00:00Z",
  regions: {
    antilles: {
      ...common,
      id: "antilles",
      label: "Antilles françaises",
      metrics: { test_acc: 0.887, test_top3: 0.965, macro_f1: 0.887 },
      classes: [
        sp("Coereba flaveola", "Sucrier à ventre jaune"),
        sp("Orthorhyncus cristatus", "Colibri huppé"),
        sp("Eulampis holosericeus", "Colibri falle-vert"),
        sp("Quiscalus lugubris", "Quiscale merle"),
        sp("Zenaida aurita", "Tourterelle à queue carrée"),
        sp("Loxigilla noctis", "Sporophile rouge-gorge"),
        sp("Tiaris bicolor", "Cici verdinère"),
        sp("Pelecanus occidentalis", "Pélican brun"),
        sp("Bubulcus ibis", "Héron garde-bœufs"),
      ],
    },
    europe: {
      ...common,
      id: "europe",
      label: "France métropolitaine",
      metrics: { test_acc: 0.808, test_top3: 0.928, macro_f1: 0.808 },
      classes: [
        sp("Turdus merula", "Merle noir"),
        sp("Erithacus rubecula", "Rougegorge familier"),
        sp("Cyanistes caeruleus", "Mésange bleue"),
        sp("Parus major", "Mésange charbonnière"),
        sp("Passer domesticus", "Moineau domestique"),
        sp("Pica pica", "Pie bavarde"),
        sp("Ardea cinerea", "Héron cendré"),
        sp("Fringilla coelebs", "Pinson des arbres"),
      ],
    },
  },
};

export async function mockScores(file: Blob, n: number): Promise<number[]> {
  const bytes = new Uint8Array(await file.slice(0, 4096).arrayBuffer());
  let seed = file.size;
  for (const b of bytes) seed = (seed * 31 + b) >>> 0;
  const scores = Array.from({ length: n }, (_, i) => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return (seed / 2 ** 32) * (i === seed % n ? 6 : 1);
  });
  const total = scores.reduce((a, b) => a + b, 0);
  return scores.map((s) => s / total);
}
