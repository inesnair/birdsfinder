# 🐦 BirdsFinder

Application d'identification d'oiseaux, avec deux modes d'entrée :

1. **📸 Photo** : un CNN fine-tuné (deep learning) renvoie les espèces les plus probables avec un pourcentage de confiance.
2. **💬 Chat** *(à venir)* : l'utilisateur décrit l'oiseau, un modèle de ML classique propose des espèces et pose des questions pour affiner.

Projet réalisé pour la formation Développeur Concepteur IA (RNCP38616, blocs 03 et 05).

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

L'API lit `models/best.pt` (chemin modifiable avec la variable `MODEL_PATH`). Sans ce fichier, elle démarre quand même mais `/predict/image` répond **503** avec un message explicite.

Pour obtenir ce fichier : entraîner le modèle (voir `docs/guide_deep_learning.md`), puis `cp runs/<modèle>/best.pt models/best.pt` et `data/classes.json` à jour.

## API

| Route | Description |
|---|---|
| `GET /health` | État du service (+ présence du fichier modèle) |
| `POST /predict/image` | Photo (multipart `file`) → top-3 espèces, confiance, drapeau `uncertain` |
| `POST /chat` | Identification par description (**501 pour l'instant**) |
| `GET /stats` | Compteurs simples : nb de requêtes, prédictions incertaines, latence moyenne |

Exemple :

```bash
curl -X POST http://localhost:8000/predict/image -F "file=@ma_photo.jpg"
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
src/            entraînement : download_data.py, train_cnn.py, predict.py, common.py
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
| Bloc 05 C4 : déploiement MLOps | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `app/` (`/stats`, logs) | ✅ socle prêt |
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
