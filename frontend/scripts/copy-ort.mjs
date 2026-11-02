// Copie les fichiers WebAssembly d'onnxruntime-web dans public/ort/.
// Ainsi le site les sert lui-même : aucun appel à un CDN tiers (meilleur pour le RGPD).
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const src = join("node_modules", "onnxruntime-web", "dist");
const dest = join("public", "ort");

if (!existsSync(src)) {
  console.warn("onnxruntime-web absent : lance d'abord `npm install`.");
  process.exit(0);
}
mkdirSync(dest, { recursive: true });
const files = readdirSync(src).filter((f) => /^ort-wasm.*\.(wasm|mjs)$/.test(f));
for (const f of files) copyFileSync(join(src, f), join(dest, f));
console.log(`onnxruntime-web : ${files.length} fichiers copiés dans ${dest}`);
