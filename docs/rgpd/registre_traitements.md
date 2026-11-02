# Registre des traitements de BirdsFinder (article 30 du RGPD)

Version bêta, projet de formation. Mise à jour : 2 novembre 2026.
Toute évolution doit être reportée ici **et** dans la page Confidentialité de l'application (`frontend/src/pages/Privacy.tsx`).

**Responsable du traitement :** Inès, porteuse du projet BirdsFinder (formation Alyra). Contact : adresse définie dans `VITE_CONTACT_EMAIL`.

## Principes de conception (article 25 : protection des données dès la conception et par défaut)

| Principe | Mise en œuvre |
|---|---|
| Minimisation | Identification sans compte et sans envoi de la photo (modèle exécuté dans le navigateur). Connexion Google limitée à `openid email profile`. |
| Par défaut | Case « lieu » décochée par défaut ; jamais de lieu pour un import depuis un ordinateur. |
| Pas de métadonnées | Photos de correction redessinées puis réencodées (EXIF, GPS et appareil supprimés), 1024 px au plus. |
| Cloisonnement | Règles Row Level Security : chaque compte ne lit et ne modifie que ses lignes ; rôle non modifiable par l'utilisateur. |
| Hébergement | Données personnelles dans Supabase, région UE (Paris). |
| Droits en libre-service | Export JSON et suppression du compte depuis la page Compte. |
| Pas de traceurs | Aucune mesure d'audience ni publicité ; stockage local strictement nécessaire (session, préférences, cache des modèles) : pas de bandeau cookies requis. |
| Âge | Compte réservé aux 15 ans et plus (article 45 de la loi Informatique et Libertés), confirmé à la première connexion. |

## Traitements

### T1. Identification d'un oiseau (sans compte)
- **Finalité :** proposer l'espèce d'un oiseau photographié.
- **Données :** aucune donnée conservée. La photo est traitée dans le navigateur (mode en ligne) ; en mode API (démo), elle est traitée en mémoire puis oubliée, sans journalisation de l'image.
- **Base légale :** sans objet (pas de collecte). Données techniques (adresse IP) vues par l'hébergeur du site et par Hugging Face lors du téléchargement des modèles.

### T2. Gestion des comptes
- **Finalité :** permettre la connexion et l'accès à l'ornithotèque.
- **Personnes :** utilisateurs de 15 ans et plus.
- **Données :** identifiant, adresse e-mail et nom Google, dates de création et de dernière connexion, statut (amateur / pro), structure (si demande pro), date d'acceptation de la politique.
- **Base légale :** exécution du service demandé (art. 6.1.b).
- **Durée :** jusqu'à la suppression par la personne ; comptes inactifs depuis 2 ans supprimés (`supabase_admin purge-inactive --apply`, à lancer chaque trimestre).
- **Destinataires :** responsable du traitement ; sous-traitants Supabase (hébergement) et Google (authentification).

### T3. Ornithotèque
- **Finalité :** garder la liste des oiseaux identifiés par la personne.
- **Données :** espèce, confiance, version du modèle, date d'observation, note libre (500 caractères au plus).
- **Base légale :** exécution du service (art. 6.1.b).
- **Durée :** jusqu'à la suppression de l'observation ou du compte.

### T4. Lieu des observations
- **Finalité :** situer ses propres observations.
- **Données :** latitude et longitude (position du téléphone ou position EXIF de la photo), source de la position.
- **Base légale :** consentement (art. 6.1.a), donné observation par observation par une case décochée par défaut.
- **Durée :** comme l'observation. Jamais publié ni partagé.
- **Point d'attention :** une suite de positions peut révéler des habitudes de déplacement : accès limité au seul titulaire, aucun usage statistique.

### T5. Corrections des professionnels (amélioration du modèle)
- **Finalité :** constituer des données d'entraînement vérifiées pour corriger les erreurs du modèle.
- **Données :** photo sans métadonnées, espèce prédite et proposée, commentaire, version du modèle, statut de vérification.
- **Base légale :** consentement explicite (art. 6.1.a), case obligatoire ; la personne atteste aussi être l'auteur de la photo et qu'elle ne montre personne de reconnaissable.
- **Durée :** jusqu'à la suppression du compte, 5 ans au plus. Limite à expliquer : un modèle déjà entraîné ne peut pas « oublier » une photo, mais elle est exclue des entraînements suivants.
- **Accès :** responsable du traitement, via la clé service (Colab), pour la vérification manuelle avant tout entraînement.

## Sous-traitants et transferts

| Prestataire | Rôle | Localisation des données | Encadrement à vérifier avant ouverture publique |
|---|---|---|---|
| Supabase | Base de données, stockage des photos de correction | UE (Paris) | DPA Supabase |
| Google | Authentification | Monde (société américaine) | Data Privacy Framework / clauses contractuelles types |
| GitHub (Microsoft) | Hébergement du site, journaux techniques | Monde | Data Privacy Framework / DPA GitHub |
| Hugging Face | Hébergement des fichiers de modèles | Monde | Conditions et DPA Hugging Face |

## Analyse d'impact (AIPD)

Pas d'AIPD obligatoire à ce stade : pas de traitement à grande échelle, pas de données sensibles, pas de profilage.
Le traitement de géolocalisation (T4) est facultatif, limité au titulaire et non exploité : à réévaluer si
l'application est ouverte au public ou si des cartes partagées sont ajoutées.

## Droits des personnes

Accès, rectification, effacement, portabilité (en libre-service dans l'appli), opposition, limitation, retrait du
consentement : par l'adresse de contact, réponse sous un mois. Réclamation possible auprès de la CNIL.

## Sécurité

HTTPS partout ; clé anon publique limitée par RLS ; clé service uniquement dans les secrets Colab ; seau de stockage
privé (JPEG, 2 Mo au plus) ; suppression de compte en cascade (profil, observations, corrections) après suppression des photos.
