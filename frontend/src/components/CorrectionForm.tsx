import { useMemo, useState } from "react";
import type { Prediction } from "../lib/classifier";
import { stripAndResize } from "../lib/image";
import type { RegionModel } from "../lib/manifest";
import { useApp } from "../state/app";
import type { PickedPhoto } from "../pages/Identify";

const OTHER = "__autre__";

/** Persona 3 : un professionnel signale une erreur. La photo part sans aucune métadonnée. */
export function CorrectionForm({ photo, predictions, model, onSent }: {
  photo: PickedPhoto;
  predictions: Prediction[];
  model: RegionModel;
  onSent: () => void;
}) {
  const { backend, notify } = useApp();
  const options = useMemo(() => [...model.classes].sort((a, b) => a.fr.localeCompare(b.fr, "fr")), [model]);
  const [proposed, setProposed] = useState("");
  const [other, setOther] = useState("");
  const [comment, setComment] = useState("");
  const [consent, setConsent] = useState(false);
  const [rights, setRights] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const top = predictions[0];
  const valid = consent && rights && (proposed === OTHER ? other.trim().length > 1 : proposed !== "" && proposed !== top.species.id);

  const send = async () => {
    if (!backend || !valid) return;
    setBusy(true);
    setError(null);
    try {
      const clean = await stripAndResize(photo.img, 1024);
      await backend.addCorrection({
        region: model.id,
        predicted_species_id: top.species.id,
        predicted_confidence: Math.round(top.confidence * 10000) / 10000,
        proposed_species_id: proposed === OTHER ? null : proposed,
        proposed_species_other: proposed === OTHER ? other.trim() : null,
        comment: comment.trim() || null,
        model_version: model.version,
        consent_training: true,
        photo: clean,
      });
      notify("Correction envoyée. Elle sera vérifiée avant d'entraîner le modèle.");
      onSent();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="panel" onSubmit={(e) => { e.preventDefault(); void send(); }}>
      <p>
        Le modèle propose <strong>{top.species.fr}</strong>. Quelle est la bonne espèce&nbsp;?
      </p>
      <label className="field">
        <span>Espèce correcte</span>
        <select value={proposed} onChange={(e) => setProposed(e.target.value)} required>
          <option value="" disabled>Choisir une espèce</option>
          {options.map((s) => (
            <option key={s.id} value={s.id} disabled={s.id === top.species.id}>
              {s.fr} ({s.sci})
            </option>
          ))}
          <option value={OTHER}>Une espèce absente de cette liste</option>
        </select>
      </label>
      {proposed === OTHER && (
        <label className="field">
          <span>Nom de l'espèce (scientifique de préférence)</span>
          <input value={other} maxLength={120} onChange={(e) => setOther(e.target.value)} placeholder="ex. Alcedo atthis" />
        </label>
      )}
      <label className="field">
        <span>Indices d'identification (facultatif)</span>
        <textarea value={comment} rows={2} maxLength={500} onChange={(e) => setComment(e.target.value)}
          placeholder="Plumage, chant entendu, critère discriminant…" />
      </label>
      <label className="check">
        <input type="checkbox" checked={rights} onChange={(e) => setRights(e.target.checked)} />
        <span>Je suis l'auteur de cette photo (ou j'ai son accord) et elle ne montre aucune personne reconnaissable.</span>
      </label>
      <label className="check">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          J'accepte que cette photo, sans ses métadonnées, soit conservée et utilisée pour entraîner les prochaines versions
          du modèle.
          <small>
            Tu peux la retirer en supprimant ton compte. Un modèle déjà entraîné ne peut pas l'oublier, mais elle ne servira
            plus aux suivants.
          </small>
        </span>
      </label>
      {error && <p className="notice danger">{error}</p>}
      <button type="submit" className="btn primary" disabled={!valid || busy}>
        {busy ? "Envoi…" : "Envoyer la correction"}
      </button>
    </form>
  );
}
