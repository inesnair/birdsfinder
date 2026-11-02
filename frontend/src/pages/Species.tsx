import { useApp, zoneIn } from "../state/app";
import { pct } from "../components/format";

export function SpeciesPage() {
  const { region } = useApp();
  if (!region) return null;
  const sorted = [...region.classes].sort((a, b) => a.fr.localeCompare(b.fr, "fr"));
  const m = region.metrics;
  return (
    <section className="page">
      <h1>Espèces connues {zoneIn(region.id)}</h1>
      <p className="lead">
        Le modèle de cette zone reconnaît ces {region.classes.length} espèces, et seulement elles. Pour un autre oiseau, il
        proposera l'espèce la plus ressemblante, en général avec une confiance basse.
      </p>
      {m && (
        <dl className="model-facts">
          <div>
            <dt>Bonne espèce en première réponse</dt>
            <dd>{m.test_acc !== undefined ? pct(m.test_acc, 1) : "non mesuré"}</dd>
          </div>
          <div>
            <dt>Bonne espèce parmi les 3 propositions</dt>
            <dd>{m.test_top3 !== undefined ? pct(m.test_top3, 1) : "non mesuré"}</dd>
          </div>
          <div>
            <dt>Modèle</dt>
            <dd>
              {region.architecture}, version {region.version}
            </dd>
          </div>
        </dl>
      )}
      <p className="muted">Mesures faites sur des photos de test que le modèle n'a jamais vues pendant son entraînement.</p>
      <ul className="species-list">
        {sorted.map((s) => (
          <li key={s.id}>
            <span>{s.fr}</span>
            <em>{s.sci}</em>
          </li>
        ))}
      </ul>
    </section>
  );
}
