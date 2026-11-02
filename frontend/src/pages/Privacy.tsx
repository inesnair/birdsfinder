import { config, demoMode } from "../config";

// Politique de confidentialité (RGPD et loi Informatique et Libertés).
// Toute évolution des traitements doit être reportée ici ET dans le registre (docs/rgpd/registre_traitements.md).
export function Privacy() {
  return (
    <section className="page narrow prose">
      <h1>Confidentialité</h1>
      <p className="lead">
        BirdsFinder est conçu pour collecter le moins de données possible : sans compte, rien n'est enregistré. Version bêta,
        réalisée dans le cadre d'une formation. Dernière mise à jour : 2 novembre 2026.
      </p>
      {demoMode && (
        <p className="notice plain">
          Cette version fonctionne en mode démo : aucune donnée ne quitte ton appareil, le compte est fictif.
        </p>
      )}

      <h2>Qui est responsable</h2>
      <p>
        Responsable du traitement : {config.controllerName}.{" "}
        {config.contactEmail ? (
          <>
            Contact pour toute question ou demande : <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a>.
          </>
        ) : (
          "Contact : par le dépôt GitHub du projet."
        )}
      </p>

      <h2>Ce que nous traitons, et pourquoi</h2>
      <table className="facts">
        <thead>
          <tr>
            <th scope="col">Usage</th>
            <th scope="col">Données</th>
            <th scope="col">Base légale</th>
            <th scope="col">Conservation</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Identifier un oiseau</th>
            <td>
              {config.inference === "onnx"
                ? "La photo est analysée sur ton appareil. Elle n'est ni envoyée ni conservée."
                : "La photo est envoyée à l'API, analysée en mémoire puis oubliée."}
            </td>
            <td>Aucune donnée personnelle collectée</td>
            <td>Aucune</td>
          </tr>
          <tr>
            <th scope="row">Compte</th>
            <td>Identifiant, nom et adresse e-mail Google, dates de création et de dernière connexion, statut (amateur ou professionnel), structure si tu demandes un compte professionnel</td>
            <td>Exécution du service que tu demandes (art. 6.1.b RGPD)</td>
            <td>Jusqu'à la suppression du compte ; comptes inactifs supprimés après 2 ans</td>
          </tr>
          <tr>
            <th scope="row">Ornithotèque</th>
            <td>Espèce, confiance, date d'observation, note facultative</td>
            <td>Exécution du service (art. 6.1.b)</td>
            <td>Jusqu'à ce que tu supprimes l'observation ou ton compte</td>
          </tr>
          <tr>
            <th scope="row">Lieu d'observation</th>
            <td>Latitude et longitude, seulement si tu coches la case (position du téléphone ou position inscrite dans la photo). Jamais pour un import depuis un ordinateur.</td>
            <td>Consentement (art. 6.1.a), case décochée par défaut</td>
            <td>Comme l'observation</td>
          </tr>
          <tr>
            <th scope="row">Corrections (comptes professionnels)</th>
            <td>Photo réduite et sans métadonnées, espèce proposée, commentaire</td>
            <td>Consentement (art. 6.1.a)</td>
            <td>Jusqu'à la suppression du compte, 5 ans au plus</td>
          </tr>
        </tbody>
      </table>
      <p>
        Aucune publicité, aucune mesure d'audience, aucun profilage. Les données ne sont ni vendues ni partagées. Les
        observations ne sont jamais publiques.
      </p>

      <h2>Qui intervient</h2>
      <ul>
        <li>Supabase : base de données et stockage des photos de correction, projet hébergé dans l'Union européenne (région Paris).</li>
        <li>Google : connexion avec ton compte Google (seuls l'identité et l'e-mail sont demandés).</li>
        <li>GitHub Pages : hébergement du site. Comme tout hébergeur, il reçoit l'adresse IP des visiteurs.</li>
        <li>Hugging Face : hébergement des fichiers des modèles, téléchargés par ton navigateur (adresse IP technique).</li>
      </ul>
      <p>
        Google, GitHub et Hugging Face sont des sociétés américaines : des données techniques peuvent être traitées hors de
        l'Union européenne. Ces transferts reposent sur les garanties prévues par le RGPD (décision d'adéquation « Data
        Privacy Framework » ou clauses contractuelles types, selon le prestataire). Le lien « Voir le lieu sur la carte »
        ouvre OpenStreetMap, un site tiers.
      </p>

      <h2>Stockage dans ton navigateur</h2>
      <p>
        BirdsFinder garde dans ton navigateur ta session de connexion, la zone choisie et, sur cet appareil, les fichiers des
        modèles pour ne pas les retélécharger. Ce stockage est nécessaire au fonctionnement : il ne demande pas de
        consentement et ne sert à aucun suivi.
      </p>

      <h2>Tes droits</h2>
      <p>
        Tu peux accéder à tes données, les rectifier, les supprimer, les récupérer (portabilité), t'opposer à leur traitement,
        en demander la limitation et retirer ton consentement à tout moment. Depuis la page Compte, tu peux directement
        télécharger tes données et supprimer ton compte. Pour toute autre demande, écris au contact ci-dessus : réponse sous
        un mois. Tu peux aussi adresser une réclamation à la CNIL (<a href="https://www.cnil.fr" target="_blank" rel="noreferrer">cnil.fr</a>).
      </p>

      <h2>Âge minimum</h2>
      <p>La création d'un compte est réservée aux personnes de 15 ans et plus. L'identification sans compte est ouverte à tous.</p>

      <h2>Sécurité</h2>
      <p>
        Connexions chiffrées (HTTPS), accès aux données limité par des règles de sécurité en base : chaque compte ne peut lire
        et modifier que ses propres données. Les photos de correction sont stockées dans un espace privé.
      </p>
    </section>
  );
}
