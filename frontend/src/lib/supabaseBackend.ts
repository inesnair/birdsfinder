// Comptes Google + données personnelles dans Supabase (projet créé en région UE).
// La sécurité ne repose PAS sur ce code : les règles RLS de supabase/schema.sql
// garantissent que chacun ne lit et n'écrit que ses propres lignes.
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { config } from "../config";
import type { Backend, Correction, NewObservation, Observation, Profile, User } from "./backend";

const BUCKET = "corrections";

function toUser(session: Session | null): User | null {
  const u = session?.user;
  if (!u) return null;
  const meta = (u.user_metadata ?? {}) as Record<string, string>;
  return { id: u.id, email: u.email ?? "", name: meta.full_name || meta.name || u.email || "Mon compte" };
}

function fail(error: { message: string } | null, what: string): void {
  if (error) throw new Error(`${what} : ${error.message}`);
}

export function createSupabaseBackend(): Backend {
  const sb: SupabaseClient = createClient(config.supabaseUrl, config.supabaseAnonKey, {
    auth: { flowType: "pkce", persistSession: true, detectSessionInUrl: true, autoRefreshToken: true },
  });

  const userId = async (): Promise<string> => {
    const { data } = await sb.auth.getSession();
    const id = data.session?.user.id;
    if (!id) throw new Error("Connecte-toi d'abord.");
    return id;
  };

  // Après le retour de Google, l'URL contient ?code=... : on la nettoie une fois la session créée.
  const cleanUrl = () => {
    if (window.location.search.includes("code=")) {
      window.history.replaceState(null, "", window.location.pathname + window.location.hash);
    }
  };

  return {
    mode: "supabase",
    async getUser() {
      const { data } = await sb.auth.getSession();
      cleanUrl();
      return toUser(data.session);
    },
    onAuthChange(cb) {
      const { data } = sb.auth.onAuthStateChange((_event, session) => {
        cleanUrl();
        cb(toUser(session));
      });
      return () => data.subscription.unsubscribe();
    },
    async signIn() {
      const { error } = await sb.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: window.location.origin + window.location.pathname,
          scopes: "openid email profile", // le strict nécessaire : identité et adresse e-mail
        },
      });
      fail(error, "Connexion Google impossible");
    },
    async signOut() {
      await sb.auth.signOut();
    },
    async getProfile() {
      const id = await userId();
      const { data, error } = await sb.from("profiles").select("*").eq("id", id).single();
      fail(error, "Profil introuvable");
      return data as Profile;
    },
    async updateProfile(update) {
      const id = await userId();
      const { data, error } = await sb.from("profiles").update(update).eq("id", id).select("*").single();
      fail(error, "Mise à jour du profil impossible");
      return data as Profile;
    },
    async listObservations() {
      const { data, error } = await sb.from("observations").select("*").order("observed_at", { ascending: false });
      fail(error, "Lecture de l'ornithotèque impossible");
      return (data ?? []) as Observation[];
    },
    async addObservation(o: NewObservation) {
      const { data, error } = await sb.from("observations").insert(o).select("*").single();
      fail(error, "Ajout à l'ornithotèque impossible");
      return data as Observation;
    },
    async deleteObservation(id) {
      const { error } = await sb.from("observations").delete().eq("id", id);
      fail(error, "Suppression impossible");
    },
    async listCorrections() {
      const { data, error } = await sb.from("corrections").select("*").order("created_at", { ascending: false });
      fail(error, "Lecture des corrections impossible");
      return (data ?? []) as Correction[];
    },
    async addCorrection(c) {
      const id = await userId();
      const { photo, ...row } = c;
      const path = `${id}/${crypto.randomUUID()}.jpg`; // 1er dossier = id de l'utilisateur (règle de stockage)
      const upload = await sb.storage.from(BUCKET).upload(path, photo, { contentType: "image/jpeg", upsert: false });
      fail(upload.error, "Envoi de la photo impossible");
      const { error } = await sb.from("corrections").insert({ ...row, photo_path: path });
      if (error) {
        await sb.storage.from(BUCKET).remove([path]); // pas de photo orpheline
        fail(error, "Envoi de la correction impossible");
      }
    },
    async exportData() {
      const { data } = await sb.auth.getSession();
      const u = data.session?.user;
      const [profile, observations, corrections] = await Promise.all([
        this.getProfile(),
        this.listObservations(),
        this.listCorrections(),
      ]);
      return {
        exported_at: new Date().toISOString(),
        account: { id: u?.id, email: u?.email, created_at: u?.created_at, last_sign_in_at: u?.last_sign_in_at, provider: "google" },
        profile,
        observations,
        corrections,
      };
    },
    async deleteAccount() {
      const id = await userId();
      // 1) photos de correction (le stockage ne se vide pas tout seul), 2) compte : le reste suit en cascade
      const { data: files } = await sb.storage.from(BUCKET).list(id, { limit: 1000 });
      if (files && files.length) {
        const removal = await sb.storage.from(BUCKET).remove(files.map((f) => `${id}/${f.name}`));
        fail(removal.error, "Suppression des photos impossible");
      }
      const { error } = await sb.rpc("delete_my_account");
      fail(error, "Suppression du compte impossible");
      await sb.auth.signOut();
    },
  };
}
