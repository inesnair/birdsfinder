import { useState } from "react";
import type { Prediction } from "../lib/classifier";
import { currentPosition, type Position } from "../lib/device";
import type { LocationSource } from "../lib/backend";
import type { RegionModel } from "../lib/manifest";
import { readStore, writeStore } from "../lib/safeStorage";
import { useApp } from "../state/app";
import type { PickedPhoto } from "../pages/Identify";
import { formatDate, pct } from "./format";

/**
 * Ajout à l'ornithotèque. Le lieu n'est enregistré que si la personne coche la case :
 *  - photo prise avec l'appareil : position actuelle du téléphone
 *  - photo de la galerie du téléphone : position inscrite dans la photo (EXIF), sinon position actuelle au choix
 *  - import depuis un ordinateur : jamais de lieu
 */
export function SaveObservation({ photo, predictions, model, onSaved }: {
  photo: PickedPhoto;
  predictions: Prediction[];
  model: RegionModel;
  onSaved: () => void;
}) {
  const { backend, notify } = useApp();
  const [speciesId, setSpeciesId] = useState(predictions[0].species.id);
  const [withPlace, setWithPlace] = useState<boolean>(() => readStore("birdsfinder-with-place", false));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exifGps = photo.meta.gps;
  const placeMode: "none" | "device" | "exif" = !photo.onPhone ? "none" : photo.source === "gallery" && exifGps ? "exif" : "device";
  const observedAt = photo.meta.takenAt ?? new Date().toISOString();

  const save = async () => {
    if (!backend) return;
    setBusy(true);
    setError(null);
    try {
      let position: Pick<Position, "latitude" | "longitude"> | null = null;
      let source: LocationSource = "none";
      if (withPlace && placeMode === "exif" && exifGps) {
        position = exifGps;
        source = "exif";
      } else if (withPlace && placeMode === "device") {
        position = await currentPosition();
        source = "device";
      }
      const chosen = predictions.find((p) => p.species.id === speciesId) ?? predictions[0];
      await backend.addObservation({
        region: model.id,
        species_id: chosen.species.id,
        species_fr: chosen.species.fr,
        species_sci: chosen.species.sci,
        confidence: Math.round(chosen.confidence * 10000) / 10000,
        model_version: model.version,
        observed_at: observedAt,
        latitude: position?.latitude ?? null,
        longitude: position?.longitude ?? null,
        location_source: source,
        note: note.trim() || null,
      });
      if (placeMode !== "none") writeStore("birdsfinder-with-place", withPlace);
      notify(`${chosen.species.fr} ajouté à ton ornithotèque`);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="panel" onSubmit={(e) => { e.preventDefault(); void save(); }}>
      <fieldset>
        <legend>Quelle espèce enregistrer&nbsp;?</legend>
        {predictions.map((p) => (
          <label key={p.species.id} className="radio">
            <input type="radio" name="species" value={p.species.id} checked={speciesId === p.species.id}
              onChange={() => setSpeciesId(p.species.id)} />
            <span>{p.species.fr}</span>
            <span className="muted">{pct(p.confidence)}</span>
          </label>
        ))}
      </fieldset>

      <p className="muted">Observé le {formatDate(observedAt, true)}{photo.meta.takenAt ? " (date de la photo)" : ""}.</p>

      {placeMode === "none" ? (
        <p className="muted">Photo importée depuis un ordinateur : l'observation est enregistrée sans lieu.</p>
      ) : (
        <label className="check">
          <input type="checkbox" checked={withPlace} onChange={(e) => setWithPlace(e.target.checked)} />
          <span>
            {placeMode === "exif"
              ? "Ajouter le lieu enregistré dans la photo"
              : photo.source === "camera"
                ? "Ajouter le lieu de l'observation (ma position actuelle)"
                : "Ajouter ma position actuelle (seulement si je suis encore sur le lieu de la photo)"}
            <small>Le lieu reste privé et tu peux le supprimer à tout moment avec l'observation.</small>
          </span>
        </label>
      )}

      <label className="field">
        <span>Note (facultatif)</span>
        <textarea value={note} maxLength={500} rows={2} onChange={(e) => setNote(e.target.value)}
          placeholder="Comportement, nombre d'individus…" />
      </label>

      {error && <p className="notice danger">{error}</p>}
      <button type="submit" className="btn primary" disabled={busy}>
        {busy ? "Ajout…" : "Ajouter"}
      </button>
    </form>
  );
}
