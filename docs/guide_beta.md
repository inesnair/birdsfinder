# Mettre BirdsFinder en ligne (bêta gratuite)

Ordre conseillé : **1 → 2 → 3 → 4**. Chaque étape se teste seule. Tant que Supabase n'est pas configuré,
l'appli fonctionne en **mode démo** (compte fictif, données gardées sur l'appareil).

Remplace `TON_COMPTE_HF` par ton identifiant Hugging Face et `inesnair` par ton identifiant GitHub si besoin.

---

## 1. Publier les modèles sur le Hugging Face Hub (Colab)

**Une seule fois :**
1. Crée un compte sur huggingface.co (gratuit).
2. Profil > Settings > Access Tokens > **Create new token**, type **Write**. Copie-le.
3. Dans Colab : icône **clé** (Secrets) à gauche > **Add new secret** : nom `HF_TOKEN`, valeur = le jeton, active « Notebook access ».

**À chaque nouveau modèle** (les photos d'entraînement doivent être dans le dossier `--data`, pour le contrôle sur le jeu de test) :

```python
%cd /content/birdsfinder
!pip -q install onnx onnxruntime

# Europe
!python -m src.export_onnx --ckpt runs_europe/convnext_tiny/best.pt --data data/raw_europe \
    --classes-json data/classes_europe.json --region europe --out export/europe
!python -m src.publish_model --export export/europe --repo TON_COMPTE_HF/birdsfinder-models

# Antilles
!python -m src.export_onnx --ckpt runs_12ep/convnext_tiny/best.pt --data data/raw \
    --classes-json data/classes.json --region antilles --out export/antilles
!python -m src.publish_model --export export/antilles --repo TON_COMPTE_HF/birdsfinder-models
```

`export_onnx` affiche l'accuracy de PyTorch, de l'ONNX complet et de l'ONNX compressé (int8) sur les mêmes photos de test.
La version int8 (environ 4 fois plus légère) n'est retenue que si elle perd au plus 1 point : **note ces chiffres pour le livret**.

Commandes utiles :
```python
!python -m src.publish_model --repo TON_COMPTE_HF/birdsfinder-models --show                      # versions en ligne
!python -m src.publish_model --repo TON_COMPTE_HF/birdsfinder-models --rollback europe --to <version>   # retour arrière
```

Adresse à retenir pour l'étape 3 : `https://huggingface.co/TON_COMPTE_HF/birdsfinder-models/resolve/main/`

---

## 2. Créer la base Supabase (comptes, ornithotèque, corrections)

1. supabase.com > **New project**. Région : **West EU (Paris)**. Note le mot de passe de la base.
2. **SQL Editor** > New query > colle tout `supabase/schema.sql` > **Run**.
3. **Project Settings > API** : note `Project URL` et la clé **anon public**.
   La clé **service_role** ne va JAMAIS dans le front ni sur GitHub : uniquement dans les secrets Colab
   (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) pour `src/supabase_admin.py`.

### Connexion Google
1. console.cloud.google.com > nouveau projet « BirdsFinder ».
2. **APIs & Services > OAuth consent screen** : type External, nom BirdsFinder, e-mail d'assistance, champs d'application
   `openid`, `email`, `profile` seulement. En mode « Testing », ajoute les adresses de ton équipe et du jury comme
   utilisateurs de test (ou publie l'application : ces champs d'application de base ne demandent pas de vérification).
3. **Credentials > Create credentials > OAuth client ID** > Web application :
   - Authorized JavaScript origins : `https://inesnair.github.io`
   - Authorized redirect URIs : `https://<ID-DU-PROJET>.supabase.co/auth/v1/callback` (adresse donnée par Supabase dans le réglage Google)
4. Supabase > **Authentication > Sign In / Providers > Google** : active, colle Client ID et Client Secret.
5. Supabase > **Authentication > URL Configuration** :
   - Site URL : `https://inesnair.github.io/birdsfinder/`
   - Redirect URLs : `https://inesnair.github.io/birdsfinder/**` et `http://localhost:5173/**`

### Valider un compte professionnel (persona 3)
Quand quelqu'un clique « Demander un compte professionnel » :
```python
!python -m src.supabase_admin pending
!python -m src.supabase_admin approve-pro adresse@exemple.fr
```

⚠️ **Projet gratuit = mise en pause après 7 jours sans activité.** Avant une démo ou la soutenance, ouvre le tableau de
bord Supabase la veille (bouton **Resume project** si besoin). Plan B : le mode démo.

---

## 3. Publier le front sur GitHub Pages

1. Dépôt GitHub > **Settings > Pages** > Source : **GitHub Actions**.
2. **Settings > Secrets and variables > Actions > onglet Variables** > New repository variable :

| Nom | Valeur |
|---|---|
| `VITE_MODELS_BASE_URL` | `https://huggingface.co/TON_COMPTE_HF/birdsfinder-models/resolve/main/` |
| `VITE_SUPABASE_URL` | Project URL Supabase |
| `VITE_SUPABASE_ANON_KEY` | clé anon public |
| `VITE_CONTACT_EMAIL` | adresse de contact RGPD |

   Ces valeurs sont publiques par nature (elles finissent dans le site) : ce sont des *variables*, pas des secrets.
   Sans les deux variables Supabase, le site est publié en **mode démo**.
3. Pousse le dossier `frontend/` sur `main` (ou onglet **Actions > Déploiement du front > Run workflow**).
4. Le site est en ligne sur `https://inesnair.github.io/birdsfinder/` (lien affiché dans l'onglet Actions).

Un nouveau modèle publié à l'étape 1 est pris en compte **au prochain chargement de la page**, sans redéployer.

---

## 4. Démo dans Colab avec l'API FastAPI (optionnel)

Pour montrer le même front branché sur l'API (`VITE_INFERENCE=api`) :
```python
%cd /content/birdsfinder/frontend
!npm install --silent && VITE_INFERENCE=api npm run build
%cd /content/birdsfinder
```
puis la cellule habituelle qui lance `uvicorn` : l'API sert le front sur `/`.

---

## Vérifications avant la soutenance

1. Ouvrir le site sur un téléphone : identification avec l'appareil photo, puis avec la galerie.
2. Se connecter avec Google, accepter la fenêtre de consentement, ajouter une observation avec et sans lieu.
3. Compte professionnel : envoyer une correction, puis `supabase_admin pending` dans Colab.
4. Compte : « Télécharger mes données » puis « Supprimer mon compte » avec un compte de test.
5. Réveiller Supabase la veille. Garder une démo prête en mode démo (`npm run dev` sans variables Supabase).
