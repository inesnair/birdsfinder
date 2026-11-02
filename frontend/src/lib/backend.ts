// Comptes, ornithotèque et corrections. Deux implémentations derrière la même interface :
//  - Supabase (en ligne, serveurs UE) quand VITE_SUPABASE_URL est renseigné
//  - Démo (tout reste dans ce navigateur) sinon : utile en local et en plan B de soutenance
import { demoMode } from "../config";
import type { RegionId } from "./manifest";

export type Role = "amateur" | "pro" | "admin";
export type LocationSource = "device" | "exif" | "none";

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface Profile {
  id: string;
  display_name: string | null;
  role: Role;
  pro_requested: boolean;
  organisation: string | null;
  terms_accepted_at: string | null;
}

export interface Observation {
  id: string;
  region: RegionId;
  species_id: string;
  species_fr: string;
  species_sci: string;
  confidence: number | null;
  model_version: string | null;
  observed_at: string;
  latitude: number | null;
  longitude: number | null;
  location_source: LocationSource;
  note: string | null;
  created_at: string;
}

export type NewObservation = Omit<Observation, "id" | "created_at">;

export interface Correction {
  id: string;
  region: RegionId;
  predicted_species_id: string;
  predicted_confidence: number;
  proposed_species_id: string | null;
  proposed_species_other: string | null;
  comment: string | null;
  model_version: string | null;
  photo_path: string;
  status: "pending" | "accepted" | "rejected";
  created_at: string;
}

export type NewCorrection = Omit<Correction, "id" | "status" | "created_at" | "photo_path"> & {
  consent_training: true;
  photo: Blob; // déjà nettoyée de ses métadonnées (stripAndResize)
};

export type ProfileUpdate = Partial<Pick<Profile, "display_name" | "pro_requested" | "organisation" | "terms_accepted_at">>;

export interface Backend {
  mode: "supabase" | "demo";
  getUser(): Promise<User | null>;
  onAuthChange(cb: (user: User | null) => void): () => void;
  signIn(): Promise<void>;
  signOut(): Promise<void>;
  getProfile(): Promise<Profile>;
  updateProfile(update: ProfileUpdate): Promise<Profile>;
  listObservations(): Promise<Observation[]>;
  addObservation(o: NewObservation): Promise<Observation>;
  deleteObservation(id: string): Promise<void>;
  listCorrections(): Promise<Correction[]>;
  addCorrection(c: NewCorrection): Promise<void>;
  exportData(): Promise<unknown>;
  deleteAccount(): Promise<void>;
  /** Mode démo uniquement : jouer le rôle d'un amateur ou d'un professionnel devant le jury. */
  setDemoRole?(role: Role): Promise<Profile>;
}

let backendPromise: Promise<Backend> | null = null;

export function getBackend(): Promise<Backend> {
  if (!backendPromise) {
    backendPromise = demoMode
      ? import("./demoBackend").then((m) => m.createDemoBackend())
      : import("./supabaseBackend").then((m) => m.createSupabaseBackend());
  }
  return backendPromise;
}

export function canCorrect(profile: Profile | null): boolean {
  return !!profile && (profile.role === "pro" || profile.role === "admin");
}
