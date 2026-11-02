import { useState } from "react";
import { useApp } from "../state/app";

/**
 * Première connexion : avant toute donnée personnelle, la personne confirme son âge
 * (15 ans minimum en France pour consentir seule) et accepte la politique de confidentialité.
 */
export function ConsentGate() {
  const { backend, user, profile, setProfile, notify } = useApp();
  const [age, setAge] = useState(false);
  const [policy, setPolicy] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!backend || !user || !profile || profile.terms_accepted_at) return null;

  const accept = async () => {
    setBusy(true);
    try {
      setProfile(await backend.updateProfile({ terms_accepted_at: new Date().toISOString() }));
      notify("Bienvenue dans BirdsFinder");
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const refuse = async () => {
    await backend.deleteAccount().catch(() => backend.signOut());
    notify("Compte supprimé : aucune donnée n'a été conservée");
  };

  return (
    <div className="modal-backdrop">
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="consent-title">
        <h2 id="consent-title">Avant de créer ton ornithotèque</h2>
        <p>
          Ton compte sert à garder les oiseaux que tu identifies, avec leur date et, si tu le choisis, le lieu de
          l'observation. Ces données ne sont jamais publiées ni partagées, et tu peux les exporter ou les supprimer à tout
          moment depuis ton compte.
        </p>
        <label className="check">
          <input type="checkbox" checked={age} onChange={(e) => setAge(e.target.checked)} />
          <span>J'ai 15 ans ou plus.</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={policy} onChange={(e) => setPolicy(e.target.checked)} />
          <span>
            J'ai lu la{" "}
            <a href="#/confidentialite" target="_blank" rel="noreferrer">
              politique de confidentialité
            </a>{" "}
            et j'accepte la création de mon compte.
          </span>
        </label>
        <div className="actions">
          <button type="button" className="btn primary" disabled={!age || !policy || busy} onClick={accept}>
            Créer mon ornithotèque
          </button>
          <button type="button" className="btn ghost" onClick={refuse}>
            Refuser et supprimer le compte
          </button>
        </div>
      </section>
    </div>
  );
}
