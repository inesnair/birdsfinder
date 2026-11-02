// Lecture minimale des métadonnées EXIF d'un JPEG : position GPS et date de prise de vue.
// Tout se passe dans le navigateur ; rien n'est envoyé. Formats non JPEG (HEIC, PNG...) : null.

export interface PhotoMetadata {
  gps: { latitude: number; longitude: number } | null;
  takenAt: string | null; // ISO 8601, heure locale de l'appareil
}

const EMPTY: PhotoMetadata = { gps: null, takenAt: null };

export async function readPhotoMetadata(file: Blob): Promise<PhotoMetadata> {
  try {
    const buffer = await file.slice(0, 256 * 1024).arrayBuffer();
    return parseExif(buffer);
  } catch {
    return EMPTY;
  }
}

export function parseExif(buffer: ArrayBuffer): PhotoMetadata {
  const view = new DataView(buffer);
  if (view.byteLength < 4 || view.getUint16(0) !== 0xffd8) return EMPTY; // pas un JPEG
  let offset = 2;
  while (offset + 4 <= view.byteLength) {
    if (view.getUint8(offset) !== 0xff) return EMPTY;
    const marker = view.getUint8(offset + 1);
    const size = view.getUint16(offset + 2);
    if (marker === 0xe1 && readAscii(view, offset + 4, 6) === "Exif\0\0") {
      return readTiff(view, offset + 10);
    }
    if (marker === 0xda) break; // début de l'image : plus de métadonnées après
    offset += 2 + size;
  }
  return EMPTY;
}

function readTiff(view: DataView, tiff: number): PhotoMetadata {
  const order = view.getUint16(tiff);
  if (order !== 0x4949 && order !== 0x4d4d) return EMPTY;
  const little = order === 0x4949;
  const u16 = (o: number) => view.getUint16(o, little);
  const u32 = (o: number) => view.getUint32(o, little);

  const readIfd = (start: number): Map<number, { type: number; count: number; valueOffset: number }> => {
    const tags = new Map<number, { type: number; count: number; valueOffset: number }>();
    if (start + 2 > view.byteLength) return tags;
    const entries = u16(start);
    for (let i = 0; i < entries; i++) {
      const entry = start + 2 + i * 12;
      if (entry + 12 > view.byteLength) break;
      tags.set(u16(entry), { type: u16(entry + 2), count: u32(entry + 4), valueOffset: entry + 8 });
    }
    return tags;
  };

  // Données de plus de 4 octets : le champ contient un décalage depuis le début du TIFF.
  const dataOffset = (tag: { type: number; count: number; valueOffset: number }) => {
    const unit = tag.type === 5 || tag.type === 10 ? 8 : tag.type === 3 ? 2 : tag.type === 4 ? 4 : 1;
    return unit * tag.count > 4 ? tiff + u32(tag.valueOffset) : tag.valueOffset;
  };
  const rationals = (tag: { type: number; count: number; valueOffset: number }) => {
    const start = dataOffset(tag);
    const values: number[] = [];
    for (let i = 0; i < tag.count; i++) {
      const den = u32(start + i * 8 + 4);
      values.push(den ? u32(start + i * 8) / den : 0);
    }
    return values;
  };
  const ascii = (tag: { type: number; count: number; valueOffset: number }) =>
    readAscii(view, dataOffset(tag), tag.count).replace(/\0+$/, "");

  const ifd0 = readIfd(tiff + u32(tiff + 4));
  let gps: PhotoMetadata["gps"] = null;
  let takenAt: string | null = null;

  const gpsPointer = ifd0.get(0x8825);
  if (gpsPointer) {
    const g = readIfd(tiff + u32(gpsPointer.valueOffset));
    const latRef = g.get(1), lat = g.get(2), lonRef = g.get(3), lon = g.get(4);
    if (latRef && lat && lonRef && lon) {
      const toDeg = (v: number[]) => v[0] + v[1] / 60 + v[2] / 3600;
      let latitude = toDeg(rationals(lat));
      let longitude = toDeg(rationals(lon));
      if (ascii(latRef).startsWith("S")) latitude = -latitude;
      if (ascii(lonRef).startsWith("W")) longitude = -longitude;
      const valid = Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 && !(latitude === 0 && longitude === 0);
      if (valid) gps = { latitude: round6(latitude), longitude: round6(longitude) };
    }
  }

  const exifPointer = ifd0.get(0x8769);
  if (exifPointer) {
    const e = readIfd(tiff + u32(exifPointer.valueOffset));
    const original = e.get(0x9003);
    if (original) takenAt = exifDateToIso(ascii(original));
  }
  if (!takenAt && ifd0.get(0x0132)) takenAt = exifDateToIso(ascii(ifd0.get(0x0132)!));

  return { gps, takenAt };
}

function exifDateToIso(value: string): string | null {
  const m = /^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/.exec(value);
  if (!m) return null;
  const date = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  return Number.isNaN(date.getTime()) || date.getTime() > Date.now() + 86400000 ? null : date.toISOString();
}

function readAscii(view: DataView, start: number, length: number): string {
  let s = "";
  for (let i = 0; i < length && start + i < view.byteLength; i++) s += String.fromCharCode(view.getUint8(start + i));
  return s;
}

const round6 = (x: number) => Math.round(x * 1e6) / 1e6;
