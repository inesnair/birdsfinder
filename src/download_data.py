"""
ÉTAPE 1 — Télécharger un dataset d'images d'oiseaux depuis iNaturalist.

Pourquoi iNaturalist ? Ce sont des observations de terrain, validées par la communauté
("research grade"), avec des photos sous licence libre : ça ressemble aux photos que
prendra un vrai utilisateur (oiseau loin, mal cadré, lumière variable).

Usage :
    python -m src.download_data --per_species 150

Résultat :
    data/raw/<espece>/<id>.jpg      <- une photo par observation
    data/classes.json               <- correspondance dossier -> nom français / scientifique
    data/credits.csv                <- auteur + licence de CHAQUE photo (à citer dans le livret)

Le script est "reprenable" : si tu le relances, il ne retélécharge pas les images déjà là.
"""
import argparse
import csv
import json
import re
import time
import unicodedata
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

API = "https://api.inaturalist.org/v1"
HEADERS = {"User-Agent": "BirdsFinder-student-project/1.0"}


def slugify(text):
    """'Mésange charbonnière' -> 'mesange_charbonniere' (nom de dossier propre)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def api_get(path, params):
    """Appel à l'API avec quelques essais si on dépasse la limite de requêtes."""
    for attempt in range(4):
        r = requests.get(f"{API}{path}", params=params, headers=HEADERS, timeout=30)
        if r.status_code == 429:  # trop de requêtes : on attend et on réessaie
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("L'API iNaturalist ne répond pas, réessaie plus tard.")


def find_taxon_id(scientific_name):
    data = api_get("/taxa", {"q": scientific_name, "rank": "species", "per_page": 5})
    for taxon in data["results"]:
        if taxon["name"].lower() == scientific_name.lower():
            return taxon["id"]
    return None


def read_species(path):
    species = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fr, sci = [part.strip() for part in line.split(";")]
        species.append((fr, sci))
    return species


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="data/species.txt")
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--per_species", type=int, default=150, help="images visées par espèce")
    ap.add_argument("--max_pages", type=int, default=8)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    classes, credits = {}, []

    for fr, sci in read_species(args.species):
        slug = slugify(fr)
        folder = out / slug
        folder.mkdir(exist_ok=True)
        classes[slug] = {"fr": fr, "sci": sci}

        have = len(list(folder.glob("*.jpg")))
        if have >= args.per_species:
            print(f"[ok]   {fr}: {have} images déjà présentes")
            continue

        taxon_id = find_taxon_id(sci)
        if taxon_id is None:
            print(f"[!!]   {fr} ({sci}) : espèce introuvable sur iNaturalist, ignorée")
            continue

        for page in range(1, args.max_pages + 1):
            if have >= args.per_species:
                break
            data = api_get("/observations", {
                "taxon_id": taxon_id,
                "quality_grade": "research",       # identification validée par la communauté
                "photos": "true",
                "photo_license": "cc0,cc-by,cc-by-nc",  # licences réutilisables
                "per_page": 100,
                "page": page,
                "order_by": "votes",
                "order": "desc",
            })
            results = data["results"]
            if not results:
                break
            for obs in results:
                if have >= args.per_species:
                    break
                photos = obs.get("photos") or []
                if not photos:
                    continue
                photo = photos[0]  # 1 seule photo par observation (évite les quasi-doublons)
                target = folder / f"{obs['id']}.jpg"
                if target.exists():
                    continue
                url = (photo.get("url") or "").replace("square", "medium")
                try:
                    img_bytes = requests.get(url, headers=HEADERS, timeout=30).content
                    img = Image.open(BytesIO(img_bytes)).convert("RGB")
                    if min(img.size) < 100:  # trop petite pour être utile
                        continue
                    img.save(target, quality=90)
                except Exception:
                    continue
                have += 1
                credits.append([slug, obs["id"], photo.get("license_code"), photo.get("attribution"), url])
            time.sleep(1)  # on reste poli avec l'API

        print(f"[done] {fr}: {have} images")

    Path("data").mkdir(exist_ok=True)
    Path("data/classes.json").write_text(json.dumps(classes, ensure_ascii=False, indent=2), encoding="utf-8")
    credits_path = Path("data/credits.csv")
    new_file = not credits_path.exists()
    with open(credits_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["espece", "observation_id", "licence", "attribution", "url"])
        writer.writerows(credits)
    print("Terminé. Pense à nettoyer à la main les images aberrantes (voir README).")


if __name__ == "__main__":
    main()
