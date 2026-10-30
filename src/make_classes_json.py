"""
Génère data/classes.json : correspondance dossier d'espèce -> nom français / scientifique.

L'API (app/inference.py) lit ce fichier pour afficher "Quiscale merle" au lieu de
"Quiscalus_lugubris". Pour le dataset des Antilles, il se construit à partir de :
  - species_counts.csv (produit par build_antilles_dataset.py, commande `count`)
  - les dossiers de photos (data/raw/<espece>/), qui donnent les classes réellement entraînées.

Usage (depuis la racine du dépôt) :
    python -m src.make_classes_json --counts /content/data_antilles/species_counts.csv --images data/raw

Nom affiché : nom français GBIF s'il existe, sinon nom anglais, sinon nom scientifique.
"""
import argparse
import csv
import json
import re
from pathlib import Path


def slug(text):
    """Même règle que build_antilles_dataset.py : c'est ce qui nomme les dossiers d'images."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--counts", required=True, help="chemin de species_counts.csv")
    ap.add_argument("--images", default="data/raw", help="dossier contenant un sous-dossier par espèce")
    ap.add_argument("--out", default="data/classes.json")
    args = ap.parse_args()

    if not Path(args.counts).is_file():
        raise SystemExit(f"Fichier introuvable : {args.counts} (lance d'abord la commande `count` du script de dataset)")
    if not Path(args.images).is_dir():
        raise SystemExit(f"Dossier introuvable : {args.images} (as-tu copié les photos dans data/raw ?)")

    with open(args.counts, encoding="utf-8") as f:
        by_slug = {slug(r["canonical_name"]): r for r in csv.DictReader(f)}

    folders = sorted(p.name for p in Path(args.images).iterdir() if p.is_dir())
    if not folders:
        raise SystemExit(f"Aucun dossier d'espèce trouvé dans {args.images}")

    classes, missing, no_french = {}, [], []
    for folder in folders:
        row = by_slug.get(folder)
        if row is None:
            missing.append(folder)
            classes[folder] = {"fr": folder.replace("_", " "), "sci": folder.replace("_", " ")}
            continue
        french = (row.get("french_name") or "").strip()
        if not french:
            no_french.append(folder)
        classes[folder] = {
            "fr": french or (row.get("english_name") or "").strip() or row["canonical_name"],
            "sci": row["canonical_name"],
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(classes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(classes)} espèces écrites dans {out}")
    if no_french:
        print(f"⚠️  {len(no_french)} sans nom français (nom anglais ou latin utilisé) : {', '.join(no_french)}")
    if missing:
        print(f"⚠️  {len(missing)} dossiers absents de {args.counts} : {', '.join(missing)}")


if __name__ == "__main__":
    main()
