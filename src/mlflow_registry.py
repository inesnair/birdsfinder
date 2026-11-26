"""
Registre de modèles LOCAL avec MLflow (remplace la publication sur le Hugging Face Hub).

Pipeline :
    Colab : train_cnn -> export_onnx            (inchangé)
    PC    : mlflow_registry register            (trace l'entraînement + enregistre une version)
            mlflow_registry promote             (met une version en "production", ou revient en arrière)
            mlflow_registry build-serving       (écrit serving/manifest.json + les .onnx lus par l'appli)

Une zone = un modèle enregistré dans MLflow : birdsfinder-antilles, birdsfinder-europe.
La version servie est celle qui porte l'alias "production".

Usage (depuis la racine du dépôt, venv activé) :
    python -m src.mlflow_registry register --export colab/export/europe --run-dir colab/runs_europe/convnext_tiny
    python -m src.mlflow_registry promote --region europe --version 2
    python -m src.mlflow_registry build-serving
    python -m src.mlflow_registry show

Interface web : mlflow ui --backend-store-uri sqlite:///mlflow.db  ->  http://127.0.0.1:5000
"""
import argparse
import datetime as dt
import json
import os
import shutil
import tempfile
from pathlib import Path

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
EXPERIMENT = "birdsfinder"
ALIAS = "production"
SERVING_DIR = Path(os.getenv("SERVING_DIR", "serving"))
MANIFEST_KEYS = ("label", "version", "architecture", "size_mb", "img_size", "resize", "mean", "std", "metrics", "classes")


def model_name(region: str) -> str:
    return f"birdsfinder-{region}"


def client():
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(TRACKING_URI)
    return mlflow, MlflowClient()


# ---------- 1. register : une exécution MLflow + une nouvelle version du modèle ----------
def register(export_dir: Path, run_dir: Path | None, promote: bool):
    mlflow, mc = client()
    card = json.loads((export_dir / "model_card.json").read_text(encoding="utf-8"))
    region, name = card["region"], model_name(card["region"])
    mlflow.set_experiment(EXPERIMENT)

    with mlflow.start_run(run_name=card["version"]) as run:
        mlflow.set_tags({"region": region, "architecture": card["architecture"], "onnx_file": card["file"]})
        mlflow.log_params({
            "region": region,
            "architecture": card["architecture"],
            "img_size": card["img_size"],
            "n_classes": len(card["classes"]),
            "onnx_file": card["file"],
        })
        # Métriques de test du fichier retenu + comparaison PyTorch / ONNX fp32 / ONNX int8
        mlflow.log_metrics({k: v for k, v in card["metrics"].items() if isinstance(v, (int, float))})
        for variant, values in card.get("evaluation", {}).items():
            mlflow.log_metrics({f"{variant}.{k}": v for k, v in values.items() if isinstance(v, (int, float))})
        mlflow.log_metric("size_mb", card["size_mb"])

        if run_dir:
            history_file = run_dir / "history.json"
            if history_file.exists():  # courbes d'apprentissage, une valeur par époque
                history = json.loads(history_file.read_text(encoding="utf-8"))
                for key, values in history.items():
                    for epoch, value in enumerate(values, start=1):
                        mlflow.log_metric(key, value, step=epoch)
            for extra in ("metrics.json", "curves.png", "confusion_matrix.png", "classification_report.json"):
                if (run_dir / extra).exists():
                    mlflow.log_artifact(str(run_dir / extra), artifact_path="reports")

        # Le modèle servi : le .onnx retenu par export_onnx + sa fiche
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "model"
            pkg.mkdir()
            shutil.copy(export_dir / card["file"], pkg / "model.onnx")
            (pkg / "model_card.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
            mlflow.log_artifacts(str(pkg), artifact_path="model")
        source = f"{run.info.artifact_uri}/model"
        run_id = run.info.run_id

    try:
        mc.create_registered_model(name, description=f"Classifieur d'oiseaux, zone {card['label']}")
    except Exception:
        pass  # déjà créé
    mv = mc.create_model_version(name, source=source, run_id=run_id,
                                 description=f"{card['version']} : accuracy test {card['metrics'].get('test_acc')}")
    mc.set_model_version_tag(name, mv.version, "label", card["version"])
    print(f"Enregistré : {name} version {mv.version} ({card['version']}, accuracy test {card['metrics'].get('test_acc')})")

    if promote:
        set_production(mc, region, mv.version)
    else:
        print(f"Pour la mettre en ligne : python -m src.mlflow_registry promote --region {region} --version {mv.version}")


# ---------- 2. promote : choisir la version servie (et revenir en arrière) ----------
def set_production(mc, region: str, version: str):
    name = model_name(region)
    mc.set_registered_model_alias(name, ALIAS, str(version))
    print(f"{name} : la version {version} porte l'alias « {ALIAS} ». Lance build-serving pour la servir.")


# ---------- 3. build-serving : MLflow -> dossier lu par l'application ----------
def build_serving(out: Path):
    mlflow, mc = client()
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    manifest = {"updated_at": now, "source": "mlflow", "regions": {}, "history": {}}

    for region in ("antilles", "europe"):
        name = model_name(region)
        try:
            prod = mc.get_model_version_by_alias(name, ALIAS)
        except Exception:
            print(f"{name} : aucune version en production, zone ignorée.")
            continue
        target = out / region / str(prod.version)
        if not (target / "model.onnx").exists():
            tmp = Path(tempfile.mkdtemp())
            local = Path(mlflow.artifacts.download_artifacts(artifact_uri=prod.source, dst_path=str(tmp)))
            target.mkdir(parents=True, exist_ok=True)
            for f in ("model.onnx", "model_card.json"):
                shutil.copy(local / f, target / f)
            shutil.rmtree(tmp, ignore_errors=True)
        card = json.loads((target / "model_card.json").read_text(encoding="utf-8"))
        entry = {k: card[k] for k in MANIFEST_KEYS if k in card}
        entry["file"] = f"{region}/{prod.version}/model.onnx"  # relatif à VITE_MODELS_BASE_URL (/models/)
        entry["registry"] = {"name": name, "version": prod.version, "alias": ALIAS, "run_id": prod.run_id}
        manifest["regions"][region] = entry
        manifest["history"][region] = [
            {"registry_version": v.version, "label": (v.tags or {}).get("label"), "run_id": v.run_id}
            for v in sorted(mc.search_model_versions(f"name='{name}'"), key=lambda v: int(v.version))
        ]
        print(f"{region} : version {prod.version} ({card['version']}) -> {target}")

    path = out / "manifest.json"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp_path.replace(path)  # écriture atomique : l'appli ne lit jamais un manifeste à moitié écrit
    print(f"Manifeste écrit : {path}. Recharge la page de l'appli pour utiliser ces versions.")


def show():
    _, mc = client()
    for region in ("antilles", "europe"):
        name = model_name(region)
        try:
            versions = sorted(mc.search_model_versions(f"name='{name}'"), key=lambda v: int(v.version))
        except Exception:
            versions = []
        if not versions:
            print(f"{name} : aucune version")
            continue
        print(name)
        for v in versions:
            mark = " <- production" if ALIAS in (v.aliases or []) else ""
            print(f"   v{v.version}  {(v.tags or {}).get('label', '')}  {v.description or ''}{mark}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="enregistrer un modèle exporté par export_onnx")
    r.add_argument("--export", required=True, type=Path, help="dossier avec model_card.json et le .onnx")
    r.add_argument("--run-dir", type=Path, help="dossier de train_cnn (history.json, curves.png...)")
    r.add_argument("--promote", action="store_true", help="mettre directement cette version en production")
    p = sub.add_parser("promote", help="mettre une version en production (sert aussi au retour arrière)")
    p.add_argument("--region", required=True, choices=["antilles", "europe"])
    p.add_argument("--version", required=True, help="numéro de version MLflow (1, 2, 3...)")
    b = sub.add_parser("build-serving", help="écrire serving/manifest.json et les modèles servis")
    b.add_argument("--out", type=Path, default=SERVING_DIR)
    sub.add_parser("show", help="lister les versions et celle en production")
    args = ap.parse_args()

    if args.cmd == "register":
        register(args.export, args.run_dir, args.promote)
    elif args.cmd == "promote":
        _, mc = client()
        set_production(mc, args.region, args.version)
    elif args.cmd == "build-serving":
        build_serving(args.out)
    else:
        show()


if __name__ == "__main__":
    main()
