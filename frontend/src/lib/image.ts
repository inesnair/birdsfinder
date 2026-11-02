// Outils image côté navigateur.

export async function loadImage(file: Blob): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return img;
  } catch {
    URL.revokeObjectURL(url);
    throw new Error("Cette image ne peut pas être lue. Essaie une photo JPEG ou PNG.");
  }
}

/**
 * Même prétraitement que src/common.py (eval_transform) :
 * côté le plus court ramené à `resize`, recadrage central `size` x `size`,
 * puis normalisation ImageNet. Résultat : tenseur [1, 3, size, size] (ordre CHW).
 */
export function imageToTensorData(img: HTMLImageElement, resize: number, size: number, mean: number[], std: number[]): Float32Array {
  const scale = resize / Math.min(img.naturalWidth, img.naturalHeight);
  const w = Math.round(img.naturalWidth * scale);
  const h = Math.round(img.naturalHeight * scale);
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Le navigateur ne permet pas d'analyser l'image.");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(img, -Math.round((w - size) / 2), -Math.round((h - size) / 2), w, h);
  const { data } = ctx.getImageData(0, 0, size, size);
  const plane = size * size;
  const out = new Float32Array(3 * plane);
  for (let i = 0; i < plane; i++) {
    for (let c = 0; c < 3; c++) {
      out[c * plane + i] = (data[i * 4 + c] / 255 - mean[c]) / std[c];
    }
  }
  return out;
}

/**
 * Copie de la photo sans aucune métadonnée (ni GPS, ni appareil, ni date) :
 * l'image est redessinée puis réencodée en JPEG, au plus `maxSide` pixels.
 * Utilisée avant d'envoyer une photo de correction.
 */
export async function stripAndResize(img: HTMLImageElement, maxSide = 1024): Promise<Blob> {
  const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.naturalWidth * scale);
  canvas.height = Math.round(img.naturalHeight * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Le navigateur ne permet pas de préparer la photo.");
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Préparation de la photo impossible."))), "image/jpeg", 0.88),
  );
}
