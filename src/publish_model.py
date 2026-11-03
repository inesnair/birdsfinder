"""
Publie un modèle exporté (src/export_onnx.py) sur le Hugging Face Hub et met à jour manifest.json.
L'application en ligne lit ce manifeste au démarrage : la nouvelle version est utilisée sans redéploiement.

Chaque version est rangée à part (<zone>/<version>/model.onnx) et l'historique est gardé dans le
manifeste : on peut revenir à une version précédente en une commande.

Usage (Colab) :
    # Jeton Hugging Face "write" dans les secrets Colab (icône clé) sous le nom HF_TOKEN
    !python -m src.publish_model --export export/europe --repo TON_COMPTE_HF/birdsfinder-models
    !python -m src.publish_model --repo TON_COMPTE_HF/birdsfinder-models --rollback europe --to 2026-11-02-convnext_tiny
    !python -m src.publish_model --repo TON_COMPTE_HF/birdsfinder-models --show
"""
import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path

MANIFEST = "manifest.json"
CARD_KEYS = ("label", "version", "architecture", "size_mb", "img_size", "resize", "mean", "std", "metrics", "classes")


def merge_manifest(manifest: dict, card: dict, file_in_repo: str, now: str) -> dict:
    """Ajoute une version au manifeste (fonction pure, testée sans réseau)."""
    manifest = json.loads(json.dumps(manifest or {}))  # copie
    manifest.setdefault("regions", {})
    manifest.setdefault("history", {})
    region = card["region"]
    entry = {k: card[k] for k in CARD_KEYS if k in card}
    entry["file"] = file_in_repo
    entry["published_at"] = now
    manifest["regions"][region] = entry
    history = [h for h in manifest["history"].get(region, []) if h["version"] != entry["version"]]
    history.append({k: v for k, v in entry.items() if k != "classes"})
    manifest["history"][region] = history
    manifest["updated_at"] = now
    return manifest


def rollback_manifest(manifest: dict, region: str, version: str, classes: list, now: str) -> dict:
    """Remet en ligne une version précédente (son fichier est toujours sur le Hub)."""
    manifest = json.loads(json.dumps(manifest))
    past = next((h for h in manifest.get("history", {}).get(region, []) if h["version"] == version), None)
    if past is None:
        known = [h["version"] for h in manifest.get("history", {}).get(region, [])]
        raise SystemExit(f"Version {version} inconnue pour {region}. Versions publiées : {known}")
    manifest["regions"][region] = {**past, "classes": classes, "published_at": now}
    manifest["updated_at"] = now
    return manifest


def model_readme(manifest: dict) -> str:
    lines = [
        "---",
        "license: cc-by-nc-4.0",
        "library_name: onnx",
        "tags: [image-classification, birds, onnx]",
        "---",
        "# BirdsFinder : modèles de reconnaissance d'oiseaux",
        "",
        "Modèles ONNX utilisés par l'application BirdsFinder (projet de formation Alyra), exécutés dans le navigateur.",
        "Entraînés sur des photos iNaturalist (qualité recherche) publiées sur GBIF sous licences CC0, CC-BY et CC-BY-NC :",
        "usage non commercial uniquement.",
        "",
        "| Zone | Version | Architecture | Espèces | Accuracy test | Top-3 test |",
        "|---|---|---|---|---|---|",
    ]
    for region, m in manifest.get("regions", {}).items():
        met = m.get("metrics", {})
        lines.append(
            f"| {m.get('label', region)} | {m['version']} | {m.get('architecture', '')} | {len(m.get('classes', []))} "
            f"| {met.get('test_acc', '')} | {met.get('test_top3', '')} |"
        )
    lines += ["", "Limites : chaque modèle ne connaît que ses espèces ; les scores de test sont un découpage aléatoire par image."]
    return "\n".join(lines) + "\n"


def hf_token() -> str:
    token = os.getenv("HF_TOKEN")
    if not token:
        try:
            from google.colab import userdata  # type: ignore

            token = userdata.get("HF_TOKEN")
        except Exception:
            token = None
    if not token:
        raise SystemExit(
            "Jeton introuvable. Les commandes !python ne voient pas les secrets Colab : dans une cellule du notebook, lance\n"
            "  import os; from google.colab import userdata; os.environ['HF_TOKEN'] = userdata.get('HF_TOKEN')"
        )
    return token


def read_manifest(api, repo: str) -> dict:
    from huggingface_hub import hf_hub_download

    if not api.file_exists(repo, MANIFEST, repo_type="model"):
        return {}
    path = hf_hub_download(repo, MANIFEST, repo_type="model", token=api.token, force_download=True)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def upload_json(api, repo: str, data, name: str, message: str):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / Path(name).name  # fichier local à plat ; son chemin dans le dépôt est path_in_repo
        p.write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        api.upload_file(path_or_fileobj=str(p), path_in_repo=name, repo_id=repo, repo_type="model", commit_message=message)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="ex. inesnair/birdsfinder-models (créé s'il n'existe pas, public)")
    ap.add_argument("--export", help="dossier produit par export_onnx (model_card.json + .onnx)")
    ap.add_argument("--rollback", metavar="ZONE", help="zone à remettre sur une version précédente")
    ap.add_argument("--to", metavar="VERSION", help="version à remettre en ligne (avec --rollback)")
    ap.add_argument("--show", action="store_true", help="afficher les versions en ligne et l'historique")
    args = ap.parse_args()

    from huggingface_hub import HfApi

    api = HfApi(token=hf_token())
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    manifest = read_manifest(api, args.repo) if api.repo_exists(args.repo) else {}

    if args.show:
        for region, m in manifest.get("regions", {}).items():
            print(f"{region} : en ligne {m['version']} ({m.get('metrics', {})})")
            for h in manifest.get("history", {}).get(region, []):
                print(f"   - {h['version']} publié le {h['published_at']}")
        return

    if args.rollback:
        if not args.to:
            raise SystemExit("Précise la version avec --to")
        classes = manifest["regions"][args.rollback]["classes"]
        manifest = rollback_manifest(manifest, args.rollback, args.to, classes, now)
        upload_json(api, args.repo, manifest, MANIFEST, f"Retour de {args.rollback} à {args.to}")
        print(f"{args.rollback} remis sur la version {args.to}. L'application l'utilisera au prochain chargement.")
        return

    if not args.export:
        raise SystemExit("Indique --export (publier), --rollback (revenir en arrière) ou --show.")
    export = Path(args.export)
    card = json.loads((export / "model_card.json").read_text(encoding="utf-8"))
    api.create_repo(args.repo, repo_type="model", exist_ok=True, private=False)  # public : le navigateur doit pouvoir le lire

    file_in_repo = f"{card['region']}/{card['version']}/model.onnx"
    print(f"Envoi de {card['file']} ({card['size_mb']} Mo) vers {args.repo}/{file_in_repo}…")
    api.upload_file(path_or_fileobj=str(export / card["file"]), path_in_repo=file_in_repo, repo_id=args.repo,
                    repo_type="model", commit_message=f"Modèle {card['region']} {card['version']}")
    upload_json(api, args.repo, card, f"{card['region']}/{card['version']}/model_card.json", "Fiche du modèle")

    manifest = merge_manifest(manifest, card, file_in_repo, now)
    upload_json(api, args.repo, model_readme(manifest), "README.md", "Fiche du dépôt")
    upload_json(api, args.repo, manifest, MANIFEST, f"Mise en ligne {card['region']} {card['version']}")  # en dernier
    print(f"En ligne : {card['region']} version {card['version']} (accuracy test {card['metrics'].get('test_acc')}).")
    print("L'application l'utilisera au prochain chargement de la page.")


if __name__ == "__main__":
    main()
