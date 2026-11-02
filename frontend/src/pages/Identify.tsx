import { useEffect, useRef, useState } from "react";
import { config } from "../config";
import { classify, isModelCached, type Prediction, type Progress } from "../lib/classifier";
import { isPhoneOrTablet } from "../lib/device";
import { readPhotoMetadata, type PhotoMetadata } from "../lib/exif";
import { loadImage } from "../lib/image";
import type { RegionModel } from "../lib/manifest";
import { canCorrect } from "../lib/backend";
import { useApp, zoneIn, zoneShortName } from "../state/app";
import { pct } from "../components/format";
import { SaveObservation } from "../components/SaveObservation";
import { CorrectionForm } from "../components/CorrectionForm";

export interface PickedPhoto {
  file: File;
  url: string;
  img: HTMLImageElement;
  source: "camera" | "gallery";
  onPhone: boolean;
  meta: PhotoMetadata;
}

type Status =
  | { kind: "idle" }
  | { kind: "working"; progress: Progress | null; needsDownload: boolean }
  | { kind: "done"; predictions: Prediction[]; model: RegionModel }
  | { kind: "error"; message: string };

export function Identify() {
  const { region, regions, setRegion, manifestError, user, profile, backend } = useApp();
  const [photo, setPhoto] = useState<PickedPhoto | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [panel, setPanel] = useState<"save" | "correct" | null>(null);
  const [attempt, setAttempt] = useState(0);
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);
  const onPhone = isPhoneOrTablet();
  const runId = useRef(0);

  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);

  // Nouvelle photo ou changement de zone : on (re)lance l'analyse.
  useEffect(() => {
    if (!photo || !region) return;
    const id = ++runId.current;
    setPanel(null);
    (async () => {
      const needsDownload = !(await isModelCached(region));
      setStatus({ kind: "working", progress: null, needsDownload });
      try {
        const predictions = await classify(region, photo.img, photo.file, (progress) => {
          if (runId.current === id) setStatus({ kind: "working", progress, needsDownload });
        });
        if (runId.current === id) setStatus({ kind: "done", predictions, model: region });
      } catch (e) {
        if (runId.current === id) setStatus({ kind: "error", message: (e as Error).message });
      }
    })();
  }, [photo, region, attempt]);

  const onFile = async (file: File | undefined, source: PickedPhoto["source"]) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setStatus({ kind: "error", message: "Ce fichier n'est pas une image. Choisis une photo." });
      return;
    }
    try {
      const img = await loadImage(file);
      // Les métadonnées ne sont lues que sur téléphone (sur ordinateur : aucune position, cf. cahier des charges)
      const meta = onPhone && source === "gallery" ? await readPhotoMetadata(file) : { gps: null, takenAt: null };
      setPhoto({ file, url: img.src, img, source, onPhone, meta });
    } catch (e) {
      setStatus({ kind: "error", message: (e as Error).message });
    }
  };

  const reset = () => {
    setPhoto(null);
    setStatus({ kind: "idle" });
    setPanel(null);
  };

  if (manifestError) {
    return (
      <section className="page">
        <h1>Les modèles ne sont pas disponibles</h1>
        <p className="lead">{manifestError}</p>
        <p>Vérifie ta connexion, puis recharge la page.</p>
      </section>
    );
  }

  const otherZone = regions.find((r) => r.id !== region?.id);
  const done = status.kind === "done" ? status : null;
  const top = done?.predictions[0];
  const uncertain = !!top && top.confidence < config.uncertainThreshold;

  return (
    <section className="page identify">
      <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden
        onChange={(e) => { void onFile(e.target.files?.[0], "camera"); e.target.value = ""; }} />
      <input ref={galleryInput} type="file" accept="image/*" hidden
        onChange={(e) => { void onFile(e.target.files?.[0], "gallery"); e.target.value = ""; }} />

      <div className="identify-grid">
        <div className="viewfinder-col">
          {!photo && (
            <div className="intro">
              <h1>Quel est cet oiseau&nbsp;?</h1>
              <p className="lead">
                Photographie un oiseau {region ? (region.id === "europe" ? "de France métropolitaine" : "des Antilles françaises") : ""}.
                {" "}
                {config.inference === "api"
                  ? "La photo est analysée par l'API du projet, puis oubliée."
                  : "L'analyse se fait sur ton appareil\u00a0: la photo n'est envoyée nulle part."}
              </p>
            </div>
          )}

          <div className={`viewfinder${photo ? " has-photo" : ""}`}>
            <span className="corner tl" /><span className="corner tr" /><span className="corner bl" /><span className="corner br" />
            {photo ? (
              <img src={photo.url} alt="Photo à identifier" />
            ) : (
              <div className="viewfinder-actions">
                {onPhone && (
                  <button type="button" className="btn primary big" onClick={() => cameraInput.current?.click()}>
                    Prendre une photo
                  </button>
                )}
                <button type="button" className={`btn big ${onPhone ? "secondary" : "primary"}`} onClick={() => galleryInput.current?.click()}>
                  {onPhone ? "Choisir dans la galerie" : "Importer une photo"}
                </button>
                <p className="hint">Un oiseau bien visible, le plus grand possible dans l'image.</p>
              </div>
            )}
          </div>

          {photo && (
            <div className="row-actions">
              <button type="button" className="btn secondary" onClick={() => (onPhone ? cameraInput : galleryInput).current?.click()}>
                {onPhone ? "Nouvelle photo" : "Autre photo"}
              </button>
              {onPhone && (
                <button type="button" className="btn ghost" onClick={() => galleryInput.current?.click()}>
                  Galerie
                </button>
              )}
              <button type="button" className="btn ghost" onClick={reset}>
                Effacer
              </button>
            </div>
          )}
        </div>

        <div className="result-col" aria-live="polite">
          {status.kind === "working" && (
            <div className="working">
              <div className="pulse" aria-hidden="true" />
              {status.progress?.phase === "download" ? (
                <>
                  <p>Téléchargement du modèle {zoneShortName(region?.id)}, une seule fois sur cet appareil.</p>
                  <progress
                    max={status.progress.total || undefined}
                    value={status.progress.total ? status.progress.loaded : undefined}
                  />
                  <p className="hint">{(status.progress.loaded / 1048576).toFixed(1).replace(".", ",")} Mo</p>
                </>
              ) : (
                <p>{status.needsDownload && !status.progress ? "Préparation du modèle…" : "Analyse de la photo…"}</p>
              )}
            </div>
          )}

          {status.kind === "error" && (
            <div className="notice danger">
              <p>{status.message}</p>
              {photo && (
                <button type="button" className="btn secondary" onClick={() => setAttempt((a) => a + 1)}>
                  Réessayer
                </button>
              )}
            </div>
          )}

          {done && top && (
            <>
              <article className={`specimen${uncertain ? " uncertain" : ""}`} aria-label="Résultat de l'identification">
                <div className="specimen-head">
                  <span>{zoneShortName(done.model.id)}</span>
                  <span>Modèle {done.model.version}</span>
                </div>
                <h2 className="specimen-name">{top.species.fr}</h2>
                <p className="specimen-sci">{top.species.sci}</p>
                <div className="confidence">
                  <span className="confidence-value">{pct(top.confidence)}</span>
                  <span className="confidence-label">de confiance</span>
                  <div className="meter" aria-hidden="true">
                    <span style={{ width: `${Math.max(2, top.confidence * 100)}%` }} />
                  </div>
                </div>
                {done.predictions.length > 1 && (
                  <ol className="alternatives" aria-label="Autres possibilités">
                    {done.predictions.slice(1).map((p) => (
                      <li key={p.species.id}>
                        <span className="alt-name">
                          {p.species.fr} <em>{p.species.sci}</em>
                        </span>
                        <span>{pct(p.confidence)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </article>

              {uncertain && (
                <div className="notice signal">
                  <p>
                    <strong>Je ne suis pas sûr de moi.</strong> Cet oiseau n'est peut-être pas parmi les{" "}
                    {done.model.classes.length} espèces que je connais {zoneIn(done.model.id)}, ou la photo est
                    difficile (oiseau petit, flou, à contre-jour).
                  </p>
                  <div className="row-actions">
                    {otherZone && (
                      <button type="button" className="btn secondary" onClick={() => setRegion(otherZone.id)}>
                        Essayer le modèle {zoneShortName(otherZone.id)}
                      </button>
                    )}
                    <a className="btn ghost" href="#/especes">
                      Voir les espèces connues
                    </a>
                  </div>
                </div>
              )}

              {!user && (
                <div className="notice plain">
                  <p>Connecte-toi avec Google pour garder cet oiseau dans ton ornithotèque.</p>
                  <button type="button" className="btn secondary" onClick={() => backend?.signIn()}>
                    Se connecter avec Google
                  </button>
                </div>
              )}

              {user && profile?.terms_accepted_at && photo && (
                <div className="after-actions">
                  <div className="row-actions">
                    <button type="button" className={`btn ${panel === "save" ? "primary" : "secondary"}`}
                      aria-expanded={panel === "save"} onClick={() => setPanel(panel === "save" ? null : "save")}>
                      Ajouter à mon ornithotèque
                    </button>
                    {canCorrect(profile) && (
                      <button type="button" className={`btn ${panel === "correct" ? "primary" : "ghost"}`}
                        aria-expanded={panel === "correct"} onClick={() => setPanel(panel === "correct" ? null : "correct")}>
                        Proposer une correction
                      </button>
                    )}
                  </div>
                  {panel === "save" && (
                    <SaveObservation photo={photo} predictions={done.predictions} model={done.model} onSaved={() => setPanel(null)} />
                  )}
                  {panel === "correct" && (
                    <CorrectionForm photo={photo} predictions={done.predictions} model={done.model} onSent={() => setPanel(null)} />
                  )}
                </div>
              )}
            </>
          )}

          {status.kind === "idle" && !photo && region && (
            <aside className="howto">
              <h2>Ce que je sais faire</h2>
              <p>
                Je reconnais {region.classes.length} espèces {region.id === "europe" ? "de France métropolitaine" : "des Antilles françaises"}.
                Change de zone en haut de l'écran si ton oiseau vient d'ailleurs.
              </p>
              <a href="#/especes">Voir la liste des espèces</a>
            </aside>
          )}
        </div>
      </div>
    </section>
  );
}
