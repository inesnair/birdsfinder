// Mode démo : un faux compte et des données gardées uniquement dans ce navigateur.
// Rien n'est envoyé nulle part. Les photos de correction ne sont pas conservées (seule leur taille).
import type { Backend, Correction, Observation, Profile, Role, User } from "./backend";
import { readStore, removeStore, writeStore } from "./safeStorage";

const KEY = "birdsfinder-demo";

interface DemoState {
  signedIn: boolean;
  profile: Profile;
  observations: Observation[];
  corrections: Correction[];
}

const DEMO_USER: User = { id: "demo-user", email: "demo@birdsfinder.local", name: "Compte de démonstration" };

const fresh = (): DemoState => ({
  signedIn: false,
  profile: {
    id: DEMO_USER.id,
    display_name: DEMO_USER.name,
    role: "amateur",
    pro_requested: false,
    organisation: null,
    terms_accepted_at: null,
  },
  observations: [],
  corrections: [],
});

const uid = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;

export function createDemoBackend(): Backend {
  let state = readStore<DemoState>(KEY, fresh());
  const listeners = new Set<(u: User | null) => void>();
  const save = () => writeStore(KEY, state);
  const emit = () => listeners.forEach((cb) => cb(state.signedIn ? DEMO_USER : null));
  const requireUser = () => {
    if (!state.signedIn) throw new Error("Connecte-toi d'abord.");
  };

  return {
    mode: "demo",
    async getUser() {
      return state.signedIn ? DEMO_USER : null;
    },
    onAuthChange(cb) {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    async signIn() {
      state.signedIn = true;
      save();
      emit();
    },
    async signOut() {
      state.signedIn = false;
      save();
      emit();
    },
    async getProfile() {
      requireUser();
      return { ...state.profile };
    },
    async updateProfile(update) {
      requireUser();
      state.profile = { ...state.profile, ...update };
      save();
      return { ...state.profile };
    },
    async setDemoRole(role: Role) {
      requireUser();
      state.profile = { ...state.profile, role, pro_requested: role === "pro" || state.profile.pro_requested };
      save();
      return { ...state.profile };
    },
    async listObservations() {
      requireUser();
      return [...state.observations].sort((a, b) => b.observed_at.localeCompare(a.observed_at));
    },
    async addObservation(o) {
      requireUser();
      const obs: Observation = { ...o, id: uid(), created_at: new Date().toISOString() };
      state.observations.push(obs);
      save();
      return obs;
    },
    async deleteObservation(id) {
      requireUser();
      state.observations = state.observations.filter((o) => o.id !== id);
      save();
    },
    async listCorrections() {
      requireUser();
      return [...state.corrections].sort((a, b) => b.created_at.localeCompare(a.created_at));
    },
    async addCorrection(c) {
      requireUser();
      if (state.profile.role === "amateur") throw new Error("Les corrections sont réservées aux comptes professionnels.");
      const { photo, consent_training: _consent, ...rest } = c;
      state.corrections.push({
        ...rest,
        id: uid(),
        status: "pending",
        created_at: new Date().toISOString(),
        photo_path: `demo/photo-non-conservee-${Math.round(photo.size / 1024)}ko.jpg`,
      });
      save();
    },
    async exportData() {
      requireUser();
      return {
        exported_at: new Date().toISOString(),
        mode: "démo (données gardées sur cet appareil)",
        account: DEMO_USER,
        profile: state.profile,
        observations: state.observations,
        corrections: state.corrections,
      };
    },
    async deleteAccount() {
      removeStore(KEY);
      state = fresh();
      emit();
    },
  };
}
