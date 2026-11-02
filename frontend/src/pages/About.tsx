import { config } from "../config";
import { useApp, zoneShortName } from "../state/app";
import { pct } from "../components/format";

export function About() {
  const { regions } = useApp();
  return (
    <section className="page narrow prose">
      <h1>Comment ça marche</h1>
      <p className="lead">
        BirdsFinder est un projet de fin de formation (concepteur développeur en intelligence artificielle, Alyra). Il
        reconnaît les oiseaux de deux zones : les Antilles françaises, peu couvertes par les applications existantes, et la
        France métropolitaine.
      </p>

      <h2>De la photo à l'espèce</h2>
      <ol className="steps">
        <li>La photo est réduite à 224 × 224 pixels et ses couleurs sont normalisées, exactement comme à l'entraînement.</li>
        <li>
          Un réseau de neurones convolutif (ConvNeXt-Tiny, pré-entraîné sur ImageNet puis spécialisé sur nos oiseaux) calcule
          un score pour chacune des 31 espèces de la zone.
        </li>
        <li>Les scores sont convertis en pourcentages ; les trois plus élevés sont affichés.</li>
        <li>Sous 50 %, l'application signale qu'elle n'est pas sûre d'elle.</li>
      </ol>
      <p>
        {config.inference === "onnx"
          ? "Ces calculs ont lieu dans ton navigateur : la photo ne quitte pas ton appareil."
          : "Dans cette version de démonstration, la photo est envoyée à l'API du projet, analysée puis oubliée."}
      </p>

      <h2>Les modèles en ligne</h2>
      <table className="facts">
        <thead>
          <tr>
            <th scope="col">Zone</th>
            <th scope="col">Espèces</th>
            <th scope="col">Bonne réponse</th>
            <th scope="col">Dans le top 3</th>
          </tr>
        </thead>
        <tbody>
          {regions.map((r) => (
            <tr key={r.id}>
              <th scope="row">{zoneShortName(r.id)}</th>
              <td>{r.classes.length}</td>
              <td>{r.metrics?.test_acc !== undefined ? pct(r.metrics.test_acc, 1) : "non mesuré"}</td>
              <td>{r.metrics?.test_top3 !== undefined ? pct(r.metrics.test_top3, 1) : "non mesuré"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        Mesures sur des photos de test jamais vues à l'entraînement. Sur les Antilles, ConvNeXt-Tiny a été retenu face à
        ResNet-18 et EfficientNet-B0, entraînés dans les mêmes conditions.
      </p>

      <h2>Les données</h2>
      <p>
        Les photos d'entraînement viennent d'observations iNaturalist de qualité « recherche », publiées sur GBIF sous
        licences CC0, CC-BY et CC-BY-NC (environ 150 photos par espèce). Les photographes sont crédités dans le jeu de données du
        projet. Les modèles sont donc diffusés pour un usage non commercial.
      </p>

      <h2>Limites connues</h2>
      <ul>
        <li>Chaque modèle ne connaît que 31 espèces : face à un autre oiseau, il répond quand même l'espèce la plus proche.</li>
        <li>Le pourcentage n'est pas une probabilité calibrée : 90 % ne veut pas dire « juste 9 fois sur 10 ».</li>
        <li>Les scores de test sont un peu optimistes, car des photos d'un même observateur peuvent être à la fois en entraînement et en test.</li>
        <li>Les espèces de chaque zone diffèrent : comparer les deux zones n'isole pas l'effet de la géographie.</li>
      </ul>

      <h2>Comment le modèle s'améliore</h2>
      <p>
        Les professionnels peuvent signaler une erreur avec la photo concernée. Chaque correction est vérifiée à la main
        avant de rejoindre les données d'entraînement. Le modèle est réentraîné sur Google Colab, comparé à la version en
        ligne, puis publié : l'application charge automatiquement la nouvelle version.
      </p>
    </section>
  );
}
