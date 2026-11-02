import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { canCorrect, type Correction, type Observation } from "../lib/backend";
import { osmLink } from "../lib/device";
import type { Species } from "../lib/manifest";
import { useApp, zoneIn, zoneShortName } from "../state/app";
import { formatDate, pct } from "../components/format";

const STATUS_LABEL: Record<Correction["status"], string> = {
  pending: "En attente de vérification",
  accepted: "Acceptée pour l'entraînement",
  rejected: "Non retenue",
};

export function Ornithotheque() {
  const { user, profile, backend, region, notify } = useApp();
  const [observations, setObservations] = useState<Observation[] | null>(null);
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const detailRef = useRef<HTMLDivElement>(null);

  // Sur téléphone, le détail s'affiche sous la grille : on l'amène à l'écran.
  useEffect(() => {
    if (!openId || !detailRef.current) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    detailRef.current.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, [openId]);

  const load = useCallback(async () => {
    if (!backend || !user || !profile?.terms_accepted_at) return;
    try {
      setObservations(await backend.listObservations());
      if (canCorrect(profile)) setCorrections(await backend.listCorrections());
    } catch (e) {
      setError((e as Error).message);
    }
  }, [backend, user, profile]);

  useEffect(() => {
    void load();
  }, [load]);

  const bySpecies = useMemo(() => {
    const map = new Map<string, Observation[]>();
    for (const o of observations ?? []) {
      if (o.region !== region?.id) continue;
      map.set(o.species_id, [...(map.get(o.species_id) ?? []), o]);
    }
    return map;
  }, [observations, region]);

  if (!user) {
    return (
      <section className="page narrow">
        <h1>Mon ornithotèque</h1>
        <p className="lead">
          Garde la trace de chaque oiseau identifié : l'espèce, la date et, si tu le souhaites, le lieu. Ta collection se
          remplit espèce après espèce.
        </p>
        <button type="button" className="btn primary" onClick={() => backend?.signIn()}>
          Se connecter avec Google
        </button>
        <p className="muted">L'identification reste possible sans compte.</p>
      </section>
    );
  }

  if (!region) return null;
  const seen = region.classes.filter((s) => bySpecies.has(s.id)).length;
  const species = [...region.classes].sort((a, b) => Number(bySpecies.has(b.id)) - Number(bySpecies.has(a.id)) || a.fr.localeCompare(b.fr, "fr"));
  const open = openId ? region.classes.find((s) => s.id === openId) ?? null : null;

  const remove = async (o: Observation) => {
    if (!backend) return;
    try {
      await backend.deleteObservation(o.id);
      notify("Observation supprimée");
      await load();
    } catch (e) {
      notify((e as Error).message);
    }
  };

  return (
    <section className="page">
      <header className="collection-head">
        <h1>Mon ornithotèque</h1>
        <p className="tally">
          <span className="tally-number">{seen}</span>
          <span>
            espèce{seen > 1 ? "s" : ""} observée{seen > 1 ? "s" : ""} sur {region.classes.length} {zoneIn(region.id)}
          </span>
        </p>
        <div className="tally-bar" aria-hidden="true">
          <span style={{ width: `${(seen / region.classes.length) * 100}%` }} />
        </div>
      </header>

      {error && <p className="notice danger">{error}</p>}
      {observations === null && !error && <p className="muted">Chargement…</p>}
      {observations?.length === 0 && (
        <div className="notice plain">
          <p>Ta collection est vide. Identifie un oiseau puis ajoute-le avec « Ajouter à mon ornithotèque ».</p>
          <a className="btn primary" href="#/">Identifier un oiseau</a>
        </div>
      )}

      <ul className="drawer" aria-label={`Espèces de la zone ${zoneShortName(region.id)}`}>
        {species.map((s) => {
          const obs = bySpecies.get(s.id);
          return (
            <li key={s.id}>
              {obs ? (
                <button type="button" className="slot seen" aria-expanded={openId === s.id} onClick={() => setOpenId(openId === s.id ? null : s.id)}>
                  <span className="slot-name">{s.fr}</span>
                  <span className="slot-sci">{s.sci}</span>
                  <span className="slot-meta">
                    {obs.length} observation{obs.length > 1 ? "s" : ""}, la dernière le {formatDate(obs[0].observed_at)}
                  </span>
                </button>
              ) : (
                <div className="slot empty">
                  <span className="slot-name">{s.fr}</span>
                  <span className="slot-sci">{s.sci}</span>
                  <span className="slot-meta">Pas encore observée</span>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <div ref={detailRef}>
        {open && <ObservationList species={open} observations={bySpecies.get(open.id) ?? []} onDelete={remove} />}
      </div>

      {canCorrect(profile) && (
        <section className="corrections">
          <h2>Mes corrections</h2>
          {corrections.length === 0 ? (
            <p className="muted">Aucune correction envoyée. Après une identification erronée, utilise « Proposer une correction ».</p>
          ) : (
            <ul className="list">
              {corrections.map((c) => (
                <li key={c.id}>
                  <span>
                    {c.predicted_species_id.replace(/_/g, " ")} corrigé en{" "}
                    <strong>{c.proposed_species_other ?? c.proposed_species_id?.replace(/_/g, " ")}</strong>
                  </span>
                  <span className={`status ${c.status}`}>{STATUS_LABEL[c.status]}</span>
                  <span className="muted">{formatDate(c.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </section>
  );
}

function ObservationList({ species, observations, onDelete }: {
  species: Species;
  observations: Observation[];
  onDelete: (o: Observation) => void;
}) {
  return (
    <section className="observations" aria-label={`Observations de ${species.fr}`}>
      <h2>{species.fr}</h2>
      <ul className="list">
        {observations.map((o) => (
          <li key={o.id}>
            <span>{formatDate(o.observed_at, true)}</span>
            <span className="muted">
              {o.latitude !== null && o.longitude !== null ? (
                <a href={osmLink(o.latitude, o.longitude)} target="_blank" rel="noreferrer">
                  Voir le lieu sur la carte
                </a>
              ) : (
                "Sans lieu"
              )}
              {o.confidence !== null && `, confiance ${pct(o.confidence)}`}
            </span>
            {o.note && <span className="note">{o.note}</span>}
            <button type="button" className="btn ghost small" onClick={() => onDelete(o)}>
              Supprimer
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
