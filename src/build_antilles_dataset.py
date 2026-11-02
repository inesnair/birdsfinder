#!/usr/bin/env python3
"""
build_antilles_dataset.py
Construit un dataset d'images d'oiseaux à partir de l'API GBIF
(observations iNaturalist "Research Grade" avec photos sous licence ouverte).

Par défaut : Antilles françaises (Guadeloupe GP, Martinique MQ).
Avec --countries : n'importe quels pays (codes à 2 lettres), par exemple FR pour la France.

Deux étapes :
  1) count    : compte les photos disponibles par espèce -> species_counts.csv
  2) download : télécharge les images des espèces retenues -> images/<espece>/*.jpg + metadata.csv

Exemples Antilles (inchangés) :
  python build_antilles_dataset.py count --out data_antilles --fr-names --nc
  python build_antilles_dataset.py download --out data_antilles --min-photos 100 --per-species 150 --nc

Exemple Europe (les 31 espèces les plus photographiées de France) :
  python build_antilles_dataset.py count --out data_europe --countries FR --fr-names --nc
  python build_antilles_dataset.py download --out data_europe --top-n 31 --per-species 150 --nc

Dépendances : pip install requests pillow
"""
import argparse
import csv
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import requests

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow est requis : pip install pillow")

GBIF = "https://api.gbif.org/v1"
INAT_DATASET = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"  # iNaturalist Research-grade Observations
AVES = 212                                             # taxonKey de la classe Aves (oiseaux)
DEFAULT_COUNTRIES = ["GP", "MQ"]                       # Guadeloupe, Martinique
COUNTRY_COLUMNS = {"GP": "guadeloupe", "MQ": "martinique"}  # noms de colonnes conservés pour les Antilles
CONFIG_NAME = "count_config.json"                      # pays utilisés au comptage, relus au téléchargement
OPEN_LICENSES = ["CC0_1_0", "CC_BY_4_0"]
NC_LICENSES = ["CC_BY_NC_4_0"]

session = requests.Session()
session.headers["User-Agent"] = "BirdsFinder-projet-formation/1.0"


# ----------------------------------------------------------------------------- utilitaires
def get(url, params=None, retries=4):
    """GET JSON avec nouvelles tentatives (GBIF peut répondre 429/5xx ponctuellement)."""
    for i in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** i)
                continue
            r.raise_for_status()
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)
    raise RuntimeError(f"Échec de la requête GBIF : {url}")


def licenses(allow_nc):
    return OPEN_LICENSES + (NC_LICENSES if allow_nc else [])


def parse_countries(text):
    codes = [c.strip().upper() for c in text.split(",") if c.strip()]
    if not codes or any(len(c) != 2 or not c.isalpha() for c in codes):
        sys.exit(f"--countries attend des codes pays à 2 lettres séparés par des virgules "
                 f"(ex. FR ou GP,MQ) ; reçu : « {text} »")
    return codes


def base_params(countries, lic):
    return {
        "datasetKey": INAT_DATASET,
        "taxonKey": AVES,
        "mediaType": "StillImage",
        "occurrenceStatus": "PRESENT",
        "country": countries,
        "license": lic,
    }


def slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def license_ok(lic, allow_nc):
    lic = (lic or "").lower()
    if "/zero/" in lic or "/by/" in lic or lic in ("cc0_1_0", "cc_by_4_0"):
        return True
    return allow_nc and ("/by-nc/" in lic or lic == "cc_by_nc_4_0")


# ----------------------------------------------------------------------------- étape 1 : count
def facet_counts(country, lic):
    params = {**base_params([country], lic), "limit": 0, "facet": "speciesKey", "facetLimit": 1500}
    data = get(f"{GBIF}/occurrence/search", params)
    facets = data.get("facets", [])
    if not facets:
        return {}
    return {int(c["name"]): c["count"] for c in facets[0]["counts"]}


def fetch_name(key, want_fr):
    sp = get(f"{GBIF}/species/{key}")
    entry = {
        "canonical": sp.get("canonicalName") or sp.get("scientificName", ""),
        "english": sp.get("vernacularName", ""),
        "french": "",
        "fr_done": False,
    }
    if want_fr:
        vn = get(f"{GBIF}/species/{key}/vernacularNames", {"limit": 200})
        for v in vn.get("results", []):
            if v.get("language") == "fra":
                entry["french"] = v.get("vernacularName", "")
                break
        entry["fr_done"] = True
    return entry


def lookup_names(keys, out, workers, want_fr):
    cache_path = out / "species_names_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    todo = [k for k in keys if str(k) not in cache or (want_fr and not cache[str(k)].get("fr_done"))]
    if todo:
        print(f"Récupération des noms de {len(todo)} espèces...")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch_name, k, want_fr): k for k in todo}
            for f in as_completed(futs):
                cache[str(futs[f])] = f.result()
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


def cmd_count(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lic = licenses(args.nc)
    countries = parse_countries(args.countries) if args.countries else list(DEFAULT_COUNTRIES)

    per_country = {}
    for c in countries:
        per_country[c] = facet_counts(c, lic)
        print(f"{c} : {sum(per_country[c].values())} observations avec photo, {len(per_country[c])} espèces")

    keys = sorted(set().union(*[set(d) for d in per_country.values()]))
    if not keys:
        sys.exit("Aucune observation trouvée : vérifie les codes pays et les licences (--nc).")
    names = lookup_names(keys, out, args.workers, args.fr_names)

    rows = []
    for k in keys:
        n = names.get(str(k), {})
        row = {
            "species_key": k,
            "canonical_name": n.get("canonical", ""),
            "english_name": n.get("english", ""),
            "french_name": n.get("french", ""),
        }
        for c in countries:
            row[COUNTRY_COLUMNS.get(c, c.lower())] = per_country[c].get(k, 0)
        row["total"] = sum(per_country[c].get(k, 0) for c in countries)
        rows.append(row)
    rows.sort(key=lambda r: -r["total"])

    csv_path = out / "species_counts.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # On mémorise les pays utilisés : l'étape download les relit toute seule.
    (out / CONFIG_NAME).write_text(json.dumps({"countries": countries, "nc": args.nc}), encoding="utf-8")

    print(f"\n=> {csv_path}")
    print("\nNombre d'espèces exploitables selon le seuil de photos par espèce :")
    for t in (30, 60, 100, 150, 300):
        print(f"  >= {t:>3} photos : {sum(1 for r in rows if r['total'] >= t)} espèces")
    print("\nTop 10 :")
    for r in rows[:10]:
        detail = " / ".join(f"{c} {per_country[c].get(r['species_key'], 0)}" for c in countries)
        print(f"  {r['total']:>5}  {r['canonical_name']}  ({detail})")


# ----------------------------------------------------------------------------- étape 2 : download
def collect_candidates(species_key, lic, allow_nc, per_species, countries):
    """Liste de photos candidates (1 photo max par observation pour limiter les quasi-doublons)."""
    found, offset = [], 0
    while len(found) < per_species:
        params = {**base_params(countries, lic), "speciesKey": species_key, "limit": 300, "offset": offset}
        data = get(f"{GBIF}/occurrence/search", params)
        results = data.get("results", [])
        for occ in results:
            for m in occ.get("media", []):
                url = m.get("identifier")
                if m.get("type") != "StillImage" or not url or not license_ok(m.get("license"), allow_nc):
                    continue
                found.append({
                    "occurrence_key": occ["key"],
                    "country": occ.get("countryCode", ""),
                    "lat": occ.get("decimalLatitude", ""),
                    "lon": occ.get("decimalLongitude", ""),
                    "date": (occ.get("eventDate") or "")[:10],
                    "creator": m.get("creator") or occ.get("recordedBy", ""),
                    "license": m.get("license", ""),
                    "source_url": url,
                })
                break  # une seule photo par observation
        if data.get("endOfRecords") or not results:
            break
        offset += 300
    return found[:per_species]


def resize_url(url, size):
    """Les URLs iNaturalist existent en plusieurs tailles : original, large, medium, small, square."""
    return re.sub(r"/(original|large|medium|small|square)\.(\w+)$", rf"/{size}.\2", url)


def download_one(cand, dest, size, max_side):
    if dest.exists():
        return True
    try:
        r = session.get(resize_url(cand["source_url"], size), timeout=40)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content))
        img.verify()                                   # détecte les fichiers corrompus
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail((max_side, max_side))
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=90)
        return True
    except Exception:
        return False


def cmd_download(args):
    out = Path(args.out)
    csv_path = out / "species_counts.csv"
    if not csv_path.exists():
        sys.exit("species_counts.csv introuvable : lance d'abord la commande 'count'.")
    lic = licenses(args.nc)

    # Pays : l'option --countries, sinon ceux du comptage (count_config.json), sinon les Antilles.
    cfg_path = out / CONFIG_NAME
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    countries = parse_countries(args.countries) if args.countries else cfg.get("countries", list(DEFAULT_COUNTRIES))
    if cfg and cfg.get("countries") != countries:
        print(f"⚠️  Pays différents du comptage ({cfg.get('countries')} -> {countries}) : "
              f"les totaux de species_counts.csv ne correspondent plus.")
    if cfg.get("nc") and not args.nc:
        print("⚠️  Le comptage utilisait --nc mais pas ce téléchargement : ajoute --nc pour garder les mêmes photos.")
    print(f"Pays : {', '.join(countries)} | licences : {', '.join(lic)}")

    excluded = {e.strip().lower() for e in args.exclude.split(",") if e.strip()}
    with open(csv_path, encoding="utf-8") as f:
        species = [r for r in csv.DictReader(f)
                   if int(r["total"]) >= args.min_photos and r["canonical_name"].lower() not in excluded]
    species.sort(key=lambda r: -int(r["total"]))
    if args.top_n:
        species = species[:args.top_n]
        print(f"{len(species)} espèces retenues (les {args.top_n} plus photographiées, au moins {args.min_photos} photos).")
    else:
        print(f"{len(species)} espèces retenues (>= {args.min_photos} photos).")

    meta_rows, failed = [], 0
    for i, sp in enumerate(species, 1):
        name = sp["canonical_name"]
        cands = collect_candidates(int(sp["species_key"]), lic, args.nc, args.per_species, countries)
        folder = out / "images" / slug(name)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {}
            for c in cands:
                dest = folder / f"{c['occurrence_key']}.jpg"
                futs[ex.submit(download_one, c, dest, args.size, args.max_side)] = (c, dest)
            ok = 0
            for f in as_completed(futs):
                c, dest = futs[f]
                if f.result():
                    ok += 1
                    meta_rows.append({
                        "species": name,
                        "french_name": sp.get("french_name", ""),
                        "species_key": sp["species_key"],
                        "local_path": str(dest.relative_to(out)),
                        **c,
                    })
                else:
                    failed += 1
        print(f"[{i}/{len(species)}] {name}: {ok}/{len(cands)} images")

    if meta_rows:
        with open(out / "metadata.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(meta_rows[0].keys()))
            w.writeheader()
            w.writerows(sorted(meta_rows, key=lambda r: (r["species"], r["occurrence_key"])))
    print(f"\nTerminé : {len(meta_rows)} images, {failed} échecs. Métadonnées : {out / 'metadata.csv'}")


# ----------------------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description="Dataset d'oiseaux (Antilles françaises par défaut) via GBIF/iNaturalist")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("count", help="compter les photos disponibles par espèce")
    c.add_argument("--out", default="data_antilles")
    c.add_argument("--countries", default=None, help="codes pays séparés par des virgules (défaut : GP,MQ ; ex. FR)")
    c.add_argument("--nc", action="store_true", help="accepter aussi CC-BY-NC (usage non commercial)")
    c.add_argument("--fr-names", action="store_true", help="récupérer les noms français (plus d'appels API)")
    c.add_argument("--workers", type=int, default=8)
    c.set_defaults(func=cmd_count)

    d = sub.add_parser("download", help="télécharger les images des espèces retenues")
    d.add_argument("--out", default="data_antilles")
    d.add_argument("--countries", default=None, help="par défaut : ceux utilisés au comptage")
    d.add_argument("--min-photos", type=int, default=60, help="seuil minimal de photos par espèce")
    d.add_argument("--top-n", type=int, default=None, help="ne garder que les N espèces les plus photographiées")
    d.add_argument("--per-species", type=int, default=150, help="nombre max de photos par espèce")
    d.add_argument("--size", default="large", choices=["original", "large", "medium"], help="taille source iNaturalist")
    d.add_argument("--max-side", type=int, default=640, help="redimensionnement (plus grand côté, en pixels)")
    d.add_argument("--exclude", default="Gallus gallus", help="espèces à exclure (noms latins séparés par des virgules)")
    d.add_argument("--nc", action="store_true", help="doit correspondre à l'option utilisée pour 'count'")
    d.add_argument("--workers", type=int, default=8)
    d.set_defaults(func=cmd_download)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
