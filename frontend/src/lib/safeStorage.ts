// localStorage peut être indisponible (navigation privée, stockage bloqué) : on ne plante jamais.
const memory = new Map<string, string>();

export function readStore<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw !== null) return JSON.parse(raw) as T;
  } catch {
    /* stockage indisponible */
  }
  const mem = memory.get(key);
  return mem !== undefined ? (JSON.parse(mem) as T) : fallback;
}

export function writeStore(key: string, value: unknown): void {
  const raw = JSON.stringify(value);
  memory.set(key, raw);
  try {
    window.localStorage.setItem(key, raw);
  } catch {
    /* on garde la copie en mémoire */
  }
}

export function removeStore(key: string): void {
  memory.delete(key);
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* rien à faire */
  }
}
