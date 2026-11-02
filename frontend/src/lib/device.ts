// Téléphone ou ordinateur ? Cela décide de l'appareil photo et de la géolocalisation
// (cahier des charges : position sur téléphone, aucune position pour un import depuis un PC).

export function isPhoneOrTablet(): boolean {
  if (typeof window === "undefined") return false;
  const coarse = window.matchMedia?.("(pointer: coarse)").matches ?? false;
  const ua = navigator.userAgent || "";
  const mobileUa = /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
  const iPadOs = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
  return (coarse && mobileUa) || iPadOs;
}

export interface Position {
  latitude: number;
  longitude: number;
  accuracy: number;
}

/** Demande la position actuelle. Le navigateur affiche sa propre demande d'autorisation. */
export function currentPosition(): Promise<Position> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Ce navigateur ne donne pas accès à la position."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) =>
        resolve({
          latitude: Math.round(p.coords.latitude * 1e6) / 1e6,
          longitude: Math.round(p.coords.longitude * 1e6) / 1e6,
          accuracy: Math.round(p.coords.accuracy),
        }),
      (err) =>
        reject(
          new Error(
            err.code === err.PERMISSION_DENIED
              ? "Position refusée. Tu peux l'autoriser dans les réglages du navigateur, ou enregistrer sans position."
              : "Position introuvable pour le moment. Réessaie à l'extérieur, ou enregistre sans position.",
          ),
        ),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  });
}

export function osmLink(latitude: number, longitude: number): string {
  return `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=15/${latitude}/${longitude}`;
}
