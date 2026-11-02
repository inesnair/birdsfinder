# 🐦 BirdsFinder

Application d'identification d'oiseaux, avec deux modes d'entrée :

1. **📸 Photo** : un CNN fine-tuné (deep learning) renvoie les espèces les plus probables avec un pourcentage de confiance.
2. **💬 Chat** *(à venir)* : l'utilisateur décrit l'oiseau, un modèle de ML classique propose des espèces et pose des questions pour affiner.

Projet réalisé pour la formation Développeur Concepteur IA (RNCP38616, blocs 03 et 05).

## Version bêta en ligne (gratuite)

```
Colab : train_cnn → export_onnx (contrôle int8 vs PyTorch) → publish_model ──► Hugging Face Hub (modèles versionnés + manifest.json)
                                                                                         │
GitHub (push sur main) ──► GitHub Actions ──► GitHub Pages : front React ◄───────────────┘  la reconnaissance tourne
                                                     │                                       dans le navigateur
                                                     └──► Supabase (UE, Paris) : comptes Google, ornithotèque, corrections
```

- **Reconnaissance dans le navigateur** (ONNX Runtime Web) : la photo ne quitte pas l'appareil.
- **Nouveau modèle en ligne sans redéploiement** : `publish_model` met à jour `manifest.json`, l'appli le relit au chargement ; retour arrière avec `--rollback`.
- **Comptes et données personnelles** dans Supabase, protégés par des règles Row Level Security (`supabase/schema.sql`).
- **Mode démo** sans Supabase : compte fictif, données gardées sur l'appareil (plan B de soutenance).
- L'API FastAPI reste disponible pour la démo Colab / Docker (`/manifest`, `/predict/image?region=`).

Mise en place pas à pas : [`docs/guide_beta.md`](docs/guide_beta.md). RGPD : [`docs/rgpd/registre_traitements.md`](docs/rgpd/registre_traitements.md).

## Démarrage rapide

### Option A : Docker (recommandé)

```bash
git lfs install            # une seule fois, avant le clone (pour récupérer le modèle)
git clone <url-du-repo> && cd birdsfinder
docker compose up --build
```

### Option B : Python local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Ouvre ensuite **http://localhost:8000** (page de démo) ou **http://localhost:8000/docs** (documentation interactive).

## Modèle

L'API sait utiliser **un modèle par zone géographique** (chargé au premier usage) :

| Zone (`region`) | Modèle | Noms des espèces | Variables d'environnement |
|---|---|---|---|
| `antilles` (par défaut) | `models/best.pt` | `data/classes.json` | `MODEL_PATH`, `CLASSES_JSON` |
| `europe` | `models/best_europe.pt` | `data/classes_europe.json` | `MODEL_PATH_EUROPE`, `CLASSES_JSON_EUROPE` |

Zone par défaut modifiable avec `DEFAULT_REGION`. Une zone sans fichier modèle répond **503** avec un message explicite, sans empêcher l'autre de fonctionner.

Pour obtenir ces fichiers : entraîner le modèle (voir `docs/guide_deep_learning.md`), puis par exemple
`cp runs_europe/convnext_tiny/best.pt models/best_europe.pt`, et `data/classes_europe.json` (généré par `python -m src.make_classes_json ... --out data/classes_europe.json`).

⚠️ Chaque modèle ne connaît que **ses 31 espèces** : une photo d'un oiseau d'une autre zone donnera quand même une réponse, éventuellement avec une confiance trompeuse. Il faut choisir la bonne zone.

## API

| Route | Description |
|---|---|
| `GET /health` | État du service (+ présence des fichiers modèles, par zone) |
| `GET /regions` | Zones proposées (Antilles, Europe) et disponibilité de leur modèle |
| `POST /predict/image?region=europe` | Photo (multipart `file`) → top-3 espèces, confiance, drapeau `uncertain` (`region` optionnel : `antilles` ou `europe`) |
| `POST /chat` | Identification par description (**501 pour l'instant**) |
| `GET /stats` | Compteurs simples : nb de requêtes (total et par zone), prédictions incertaines, latence moyenne |

Exemple :

```bash
curl -X POST "http://localhost:8000/predict/image?region=europe" -F "file=@ma_photo.jpg"
```

Quand la confiance du meilleur résultat est inférieure à `CONFIDENCE_THRESHOLD` (0,5 par défaut), la réponse contient `"uncertain": true` et suggère de passer en mode chat.

## Reproduire l'entraînement

```bash
pip install -r requirements-train.txt
python -m src.download_data --per_species 150          # images iNaturalist + data/credits.csv
python -m src.train_cnn --model resnet18 --epochs 12   # idem avec efficientnet_b0, convnext_tiny
python -m src.predict ma_photo.jpg --ckpt runs/resnet18/best.pt
```

Un GPU est recommandé (Google Colab convient). Détails et explications : `docs/guide_deep_learning.md`.

## Tests et CI

```bash
pip install -r requirements-ci.txt
pytest
```

Les tests de l'API utilisent un prédicteur factice (aucun modèle requis). Un test supplémentaire charge un vrai mini-modèle et est ignoré automatiquement si `torch` n'est pas installé. La CI GitHub Actions (`.github/workflows/ci.yml`) lance lint, tests et un build Docker à chaque push.

## Structure

```
app/            API FastAPI (main.py, inference.py, config.py, static/index.html)
frontend/       application React (Vite) : identification, ornithotèque, corrections, pages RGPD
src/            entraînement : build_antilles_dataset.py, train_cnn.py, predict.py, common.py
                mise en production : export_onnx.py, publish_model.py ; administration : supabase_admin.py
supabase/       schema.sql (tables, règles de sécurité RLS, stockage, suppression de compte)
models/         modèles entraînés (Git LFS)
data/           species.txt, classes.json, credits.csv (les images ne sont pas versionnées)
reports/        courbes, matrices de confusion, métriques (preuves pour le livret)
tests/          tests pytest
docs/           guides
```

## Où trouver la preuve de chaque compétence

| Compétence | Où | Statut |
|---|---|---|
| Bloc 05 C1 : données non structurées → numériques | `src/train_cnn.py` (transformations), `src/common.py` | ✅ code prêt |
| Bloc 05 C2 : choix de l'architecture profonde | `reports/` (tableau comparatif à produire) | ⏳ à faire |
| Bloc 05 C3 : entraînement, loss | `src/train_cnn.py`, courbes dans `reports/` | ⏳ à lancer |
| Bloc 05 C4 : déploiement MLOps | `src/export_onnx.py` (packaging + contrôle de non-régression), `src/publish_model.py` (versionnement, rollback), `.github/workflows/` (CI + déploiement), `frontend/`, `Dockerfile`, `app/` (`/stats`, logs) | ✅ bêta |
| Bloc 03 C1–C3 : ML classique | à venir (mode chat) | ⏳ à faire |

## Données et licences

Photos issues d'iNaturalist (observations « research grade », licences CC0 / CC-BY / CC-BY-NC). Auteur et licence de chaque photo : `data/credits.csv`. Usage pédagogique uniquement.

## Publier sur GitHub

1. GitHub → **New repository** → nom `birdsfinder`, **sans** cocher « Add a README », `.gitignore` ni licence. Choisis *Public*, ou *Private* en ajoutant les correcteurs comme collaborateurs (Settings → Collaborators).
2. Dans le dossier du projet :
   ```bash
   git init -b main
   git lfs install
   git add .
   git commit -m "Initial commit : squelette BirdsFinder"
   git remote add origin https://github.com/<ton-utilisateur>/birdsfinder.git
   git push -u origin main
   ```
3. Onglet **Actions** : la CI se lance toute seule.

> Git LFS sur GitHub a un quota gratuit limité (de l'ordre du Go de stockage et de bande passante par mois) : suffisant pour un ou deux modèles légers. Si tu le dépasses, publie le modèle dans **Releases** (onglet « Releases » du repo) et télécharge-le dans `models/best.pt` avant de lancer l'API.
