# 🐦 Guide : entraîner le modèle photo (Deep Learning)

## Comprendre ce qu'on fait (à savoir expliquer en soutenance)

| Mot | Explication simple |
|---|---|
| **Transfer learning** | On part d'un réseau déjà entraîné sur 1,2 M d'images (ImageNet) : il sait déjà voir des formes, textures, plumages. On ne réapprend que la fin. |
| **Fine-tuning** | On "affine" ensuite tout le réseau avec un petit learning rate, pour qu'il s'adapte à nos oiseaux. |
| **Loss** | Un nombre qui mesure à quel point le modèle se trompe. Entraîner = faire baisser ce nombre. Ici : *CrossEntropy*. |
| **Époque** | Un passage complet sur toutes les images d'entraînement. |
| **Batch** | Un petit paquet d'images traité d'un coup (32 ici). |
| **Train / Val / Test** | Train : le modèle apprend dessus. Val : on s'en sert pour choisir le meilleur modèle. Test : images jamais vues, pour la note finale honnête. |
| **Overfitting** | Le modèle apprend les images par cœur : loss train ↘ mais loss val ↗. On le combat avec l'augmentation de données et l'early stopping. |
| **Softmax** | Transforme les scores du modèle en probabilités (somme = 100 %) → ton pourcentage de confiance. |

## Entraîner sur Google Colab (GPU)

1. Colab → *Exécution* → *Modifier le type d'exécution* → **GPU (T4)**.
2. Récupère le projet (`git clone <url GitHub>` ou dépose le dossier), puis, dans une cellule :
   ```
   %cd birdsfinder
   !pip install -r requirements-train.txt
   # essai court d'abord, pour vérifier que tout tourne :
   !python -m src.download_data --per_species 30
   !python -m src.train_cnn --model resnet18 --epochs 3
   # puis le vrai entraînement :
   !python -m src.download_data --per_species 150
   !python -m src.train_cnn --model resnet18 --epochs 12
   !python -m src.train_cnn --model efficientnet_b0 --epochs 12
   !python -m src.train_cnn --model convnext_tiny --epochs 12
   ```
3. Télécharge `runs/` et `data/classes.json`/`data/credits.csv` (Colab efface tout à la fermeture).
4. Dans le repo : copie le modèle choisi dans `models/best.pt`, et les courbes / métriques dans `reports/`.

## Ce que tu dois faire toi-même (et qui fait la valeur du livret)

1. **Regarder tes données** : ouvre quelques dossiers, supprime les images aberrantes (œufs, cartes, oiseau minuscule).
2. **Comparer les 3 modèles** : tableau avec `metrics.json` de chacun (accuracy, top-3, macro-F1, taille, temps par époque), puis justifier ton choix (Bloc 05 C2).
3. **Lire tes courbes** (`curves.png`) : repère l'overfitting, explique-le.
4. **Lire la matrice de confusion** : quelles espèces se confondent, et pourquoi (ex. mésange noire / nonnette).
5. **Citer les sources** : `data/credits.csv` contient auteur et licence de chaque photo.
6. **Expérimenter** : change un réglage (learning rate, époques, augmentation), relance, compare, explique l'effet.

## Questions de jury à savoir traiter sans aide

- Pourquoi du transfer learning plutôt qu'un réseau from scratch ?
- Pourquoi geler le réseau au début, puis le dégeler ?
- Que montre votre courbe de validation ? Y a-t-il de l'overfitting ?
- Pourquoi ce modèle plutôt qu'un autre ?
- Que signifie le pourcentage affiché, et est-il fiable ?
