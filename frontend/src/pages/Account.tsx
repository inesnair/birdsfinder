import { useState } from "react";
import type { Role } from "../lib/backend";
import { useApp } from "../state/app";
import { downloadJson } from "../components/format";

const ROLE_LABEL: Record<Role, string> = {
  amateur: "Amateur",
  pro: "Professionnel (corrections activées)",
  admin: "Administratrice",
};

export function Account() {
  const { user, profile, backend, setProfile, notify } = useApp();
  const [organisation, setOrganisation] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!user) {
    return (
      <section className="page narrow">
        <h1>Compte</h1>
        <p className="lead">Un compte Google te permet de garder tes observations dans ton ornithotèque.</p>
        <ul className="plain-list">
          <li>Sans compte : identification illimitée, rien n'est enregistré.</li>
          <li>Avec un compte : ornithotèque privée, avec le lieu si tu le choisis.</li>
          <li>Compte professionnel : tu peux aussi proposer des corrections pour améliorer le modèle.</li>
        </ul>
        <button type="button" className="btn primary" onClick={() => backend?.signIn()}>
          Se connecter avec Google
        </button>
        <p className="muted">
          Seuls ton nom et ton adresse e-mail Google sont transmis. Détails dans la <a href="#/confidentialite">politique de confidentialité</a>.
        </p>
      </section>
    );
  }

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page narrow">
      <h1>Compte</h1>
      <dl className="account-facts">
        <div>
          <dt>Nom</dt>
          <dd>{user.name}</dd>
        </div>
        <div>
          <dt>E-mail</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt>Statut</dt>
          <dd>{profile ? ROLE_LABEL[profile.role] : "…"}</dd>
        </div>
      </dl>

      {backend?.mode === "demo" && backend.setDemoRole && profile && (
        <section className="panel">
          <h2>Mode démo : choisir un profil</h2>
          <p className="muted">Pour montrer les trois parcours sans vrai compte.</p>
          <div className="row-actions">
            {(["amateur", "pro"] as Role[]).map((r) => (
              <button key={r} type="button" className={`btn ${profile.role === r ? "primary" : "secondary"}`}
                onClick={() => run(async () => setProfile(await backend.setDemoRole!(r)))}>
                {r === "amateur" ? "Amateur confirmé" : "Professionnel"}
              </button>
            ))}
          </div>
        </section>
      )}

      {profile?.role === "amateur" && backend?.mode === "supabase" && (
        <section className="panel">
          <h2>Compte professionnel</h2>
          {profile.pro_requested ? (
            <p>Demande envoyée{profile.organisation ? ` pour ${profile.organisation}` : ""}. Elle sera validée manuellement.</p>
          ) : (
            <form onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                setProfile(await backend.updateProfile({ pro_requested: true, organisation: organisation.trim() || null }));
                notify("Demande de compte professionnel envoyée");
              });
            }}>
              <p>Ornithologue, bureau d'études, association naturaliste : tu peux proposer des corrections au modèle.</p>
              <label className="field">
                <span>Structure</span>
                <input value={organisation} maxLength={120} onChange={(e) => setOrganisation(e.target.value)} required />
              </label>
              <button type="submit" className="btn secondary" disabled={busy}>Demander un compte professionnel</button>
            </form>
          )}
        </section>
      )}

      <section className="panel">
        <h2>Mes données</h2>
        <p>Télécharge tout ce que BirdsFinder garde sur toi, dans un fichier lisible (JSON).</p>
        <button type="button" className="btn secondary" disabled={busy}
          onClick={() => run(async () => downloadJson(await backend!.exportData(), "birdsfinder-mes-donnees.json"))}>
          Télécharger mes données
        </button>
      </section>

      <section className="panel danger-zone">
        <h2>Supprimer mon compte</h2>
        <p>Ton compte, ton ornithotèque et tes photos de correction sont supprimés définitivement.</p>
        {confirmDelete ? (
          <div className="row-actions">
            <button type="button" className="btn danger" disabled={busy}
              onClick={() => run(async () => { await backend!.deleteAccount(); notify("Compte supprimé"); window.location.hash = "#/"; })}>
              Confirmer la suppression
            </button>
            <button type="button" className="btn ghost" onClick={() => setConfirmDelete(false)}>Annuler</button>
          </div>
        ) : (
          <button type="button" className="btn ghost" onClick={() => setConfirmDelete(true)}>Supprimer mon compte</button>
        )}
      </section>

      <button type="button" className="btn ghost" onClick={() => backend?.signOut()}>Se déconnecter</button>
    </section>
  );
}
