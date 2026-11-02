import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getBackend, type Backend, type Profile, type User } from "../lib/backend";
import { availableRegions, loadManifest, type Manifest, type RegionId, type RegionModel } from "../lib/manifest";
import { readStore, writeStore } from "../lib/safeStorage";

interface AppState {
  manifest: Manifest | null;
  manifestError: string | null;
  regions: RegionModel[];
  region: RegionModel | null;
  setRegion: (id: RegionId) => void;
  backend: Backend | null;
  user: User | null;
  profile: Profile | null;
  authReady: boolean;
  refreshProfile: () => Promise<void>;
  setProfile: (p: Profile | null) => void;
  toast: string | null;
  notify: (message: string) => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const [regionId, setRegionId] = useState<RegionId>(() => readStore<RegionId>("birdsfinder-zone", "antilles"));
  const [backend, setBackend] = useState<Backend | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    loadManifest()
      .then(setManifest)
      .catch((e: Error) => setManifestError(e.message));
  }, []);

  useEffect(() => {
    let unsubscribe = () => {};
    getBackend()
      .then(async (b) => {
        setBackend(b);
        setUser(await b.getUser());
        unsubscribe = b.onAuthChange(setUser);
      })
      .catch(() => setUser(null))
      .finally(() => setAuthReady(true));
    return () => unsubscribe();
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!backend || !user) {
      setProfile(null);
      return;
    }
    try {
      setProfile(await backend.getProfile());
    } catch {
      setProfile(null);
    }
  }, [backend, user]);

  useEffect(() => {
    void refreshProfile();
  }, [refreshProfile]);

  const regions = useMemo(() => availableRegions(manifest), [manifest]);
  const region = regions.find((r) => r.id === regionId) ?? regions[0] ?? null;

  const setRegion = useCallback((id: RegionId) => {
    setRegionId(id);
    writeStore("birdsfinder-zone", id);
  }, []);

  const notify = useCallback((message: string) => {
    setToast(message);
    window.setTimeout(() => setToast((t) => (t === message ? null : t)), 3500);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.zone = region?.id ?? "antilles";
  }, [region]);

  const value: AppState = {
    manifest,
    manifestError,
    regions,
    region,
    setRegion,
    backend,
    user,
    profile,
    authReady,
    refreshProfile,
    setProfile,
    toast,
    notify,
  };
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp doit être utilisé dans <AppProvider>");
  return ctx;
}

// Navigation par ancre (#/...) : fonctionne sur GitHub Pages sans réglage serveur.
export function useRoute(): string {
  const read = () => window.location.hash.replace(/^#/, "") || "/";
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const onChange = () => {
      setRoute(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

export function zoneShortName(id: RegionId | undefined): string {
  return id === "europe" ? "France métropolitaine" : "Antilles";
}

/** « aux Antilles », « en France métropolitaine » */
export function zoneIn(id: RegionId | undefined): string {
  return id === "europe" ? "en France métropolitaine" : "aux Antilles";
}

/** Libellé court du sélecteur de zone (doit tenir sur un téléphone) */
export function zoneTabName(id: RegionId | undefined): string {
  return id === "europe" ? "Métropole" : "Antilles";
}
