import { useApp, zoneShortName, zoneTabName } from "../state/app";

/** Choix du modèle : chaque zone a son propre modèle de 31 espèces. */
export function ZoneSwitch() {
  const { regions, region, setRegion } = useApp();
  if (regions.length === 0) return null;
  return (
    <div className="zone-switch" role="radiogroup" aria-label="Zone d'observation">
      {regions.map((r) => (
        <button
          key={r.id}
          type="button"
          role="radio"
          aria-checked={region?.id === r.id}
          data-zone={r.id}
          onClick={() => setRegion(r.id)}
        >
          <span aria-hidden="true">{zoneTabName(r.id)}</span>
          <span className="sr-only">{zoneShortName(r.id)}</span>
        </button>
      ))}
    </div>
  );
}
