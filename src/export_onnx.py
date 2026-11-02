"""
Exporte un modèle entraîné (best.pt) au format ONNX pour la reconnaissance DANS LE NAVIGATEUR,
le compresse (quantification int8) et vérifie, sur le jeu de test, qu'il répond comme PyTorch.

C'est l'étape « packaging » du pipeline MLOps :
    entraînement (train_cnn) -> export + contrôle (ce script) -> publication (publish_model)

Usage (Colab, depuis la racine du dépôt) :
    !pip -q install onnx onnxruntime
    !python -m src.export_onnx --ckpt runs_europe/convnext_tiny/best.pt --data data/raw_europe \\
        --classes-json data/classes_europe.json --region europe --out export/europe

Produit dans --out :
    model_fp32.onnx      modèle complet (environ la taille de best.pt)
    model_int8.onnx      modèle compressé (environ 4 fois plus léger), si sa précision tient
    model_card.json      fiche lue par l'application : espèces, prétraitement, métriques, version
"""
import argparse
import datetime as dt
import inspect
import json
from pathlib import Path

import numpy as np

REGION_LABELS = {"antilles": "Antilles françaises", "europe": "France métropolitaine"}
RESIZE = 256  # transforms.Resize(256) de eval_transform


def export_fp32(model, path: Path, img_size: int):
    import torch

    dummy = torch.randn(1, 3, img_size, img_size)
    kwargs = dict(
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )
    if "dynamo" in inspect.signature(torch.onnx.export).parameters:
        kwargs["dynamo"] = False  # exporteur classique : le plus compatible avec onnxruntime-web
    torch.onnx.export(model, dummy, str(path), **kwargs)


def quantize_int8(src: Path, dst: Path):
    from onnxruntime.quantization import QuantType, quantize_dynamic

    # Seules les couches denses (MatMul/Gemm) sont compressées : c'est l'essentiel des poids de ConvNeXt,
    # et ces opérations sont bien prises en charge par onnxruntime-web.
    quantize_dynamic(str(src), str(dst), weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul", "Gemm"])


def test_subset(data_dir: str, seed: int):
    """Exactement le même découpage 70/15/15 que train_cnn.py : on évalue sur les mêmes photos de test."""
    from sklearn.model_selection import train_test_split
    from torchvision import datasets

    from src.common import eval_transform

    probe = datasets.ImageFolder(data_dir)
    targets = probe.targets
    idx = list(range(len(targets)))
    _, rest_idx = train_test_split(idx, test_size=0.30, stratify=targets, random_state=seed)
    rest_targets = [targets[i] for i in rest_idx]
    _, test_idx = train_test_split(rest_idx, test_size=0.50, stratify=rest_targets, random_state=seed)
    ds = datasets.ImageFolder(data_dir, transform=eval_transform())
    return ds, test_idx, probe.classes


def evaluate(ds, test_idx, torch_model, sessions, limit=None):
    """Logits PyTorch et ONNX sur le test -> accuracy, top-3, macro-F1, accord avec PyTorch."""
    import torch
    from sklearn.metrics import f1_score

    indices = test_idx[:limit] if limit else test_idx
    y_true, preds = [], {"pytorch": [], **{name: [] for name in sessions}}
    top3 = {name: 0 for name in preds}
    max_diff = {name: 0.0 for name in sessions}
    for n, i in enumerate(indices, 1):
        x, y = ds[i]
        y_true.append(y)
        with torch.no_grad():
            ref = torch_model(x.unsqueeze(0)).numpy()[0]
        outputs = {"pytorch": ref}
        for name, sess in sessions.items():
            out = sess.run(None, {"image": x.unsqueeze(0).numpy()})[0][0]
            outputs[name] = out
            max_diff[name] = max(max_diff[name], float(np.abs(out - ref).max()))
        for name, logits in outputs.items():
            order = np.argsort(-logits)
            preds[name].append(int(order[0]))
            top3[name] += int(y in order[:3])
        if n % 100 == 0:
            print(f"  {n}/{len(indices)} images évaluées")
    results = {}
    for name in preds:
        acc = float(np.mean(np.array(preds[name]) == np.array(y_true)))
        results[name] = {
            "test_acc": round(acc, 4),
            "test_top3": round(top3[name] / len(y_true), 4),
            "macro_f1": round(float(f1_score(y_true, preds[name], average="macro", zero_division=0)), 4),
            "n_test": len(y_true),
        }
        if name != "pytorch":
            agree = float(np.mean(np.array(preds[name]) == np.array(preds["pytorch"])))
            results[name]["agreement_with_pytorch"] = round(agree, 4)
            results[name]["max_logit_diff"] = round(max_diff[name], 4)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True, help="best.pt produit par train_cnn")
    ap.add_argument("--data", required=True, help="dossier d'images utilisé pour l'entraînement (pour le jeu de test)")
    ap.add_argument("--classes-json", required=True, help="noms français / scientifiques (make_classes_json)")
    ap.add_argument("--region", required=True, choices=sorted(REGION_LABELS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", default=None, help="par défaut : AAAA-MM-JJ-<architecture>")
    ap.add_argument("--max-drop", type=float, default=0.01, help="perte d'accuracy tolérée pour garder la version int8")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=None, help="(tests rapides) nombre max d'images de test")
    args = ap.parse_args()

    import onnxruntime as ort
    import torch

    from src.common import build_model

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ckpt = torch.load(args.ckpt, map_location="cpu")
    classes = ckpt["classes"]
    arch = ckpt["model"]
    img_size = ckpt.get("img_size", 224)
    model, _ = build_model(arch, len(classes), pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    ds, test_idx, data_classes = test_subset(args.data, args.seed)
    if data_classes != classes:
        raise SystemExit("Les dossiers de --data ne correspondent pas aux classes du modèle : mauvais dossier ?")

    print("1/3 Export ONNX…")
    fp32 = out / "model_fp32.onnx"
    export_fp32(model, fp32, img_size)
    print("2/3 Compression int8…")
    int8 = out / "model_int8.onnx"
    quantize_int8(fp32, int8)

    print(f"3/3 Contrôle sur {len(test_idx[: args.limit] if args.limit else test_idx)} photos de test…")
    opts = ort.SessionOptions()
    sessions = {
        "onnx_fp32": ort.InferenceSession(str(fp32), opts, providers=["CPUExecutionProvider"]),
        "onnx_int8": ort.InferenceSession(str(int8), opts, providers=["CPUExecutionProvider"]),
    }
    results = evaluate(ds, test_idx, model, sessions, args.limit)

    drop = results["pytorch"]["test_acc"] - results["onnx_int8"]["test_acc"]
    chosen = "model_int8.onnx" if drop <= args.max_drop else "model_fp32.onnx"
    chosen_key = "onnx_int8" if chosen == "model_int8.onnx" else "onnx_fp32"

    names = json.loads(Path(args.classes_json).read_text(encoding="utf-8"))
    card = {
        "region": args.region,
        "label": REGION_LABELS[args.region],
        "version": args.version or f"{dt.date.today().isoformat()}-{arch}",
        "architecture": arch,
        "file": chosen,
        "size_mb": round((out / chosen).stat().st_size / 1e6, 1),
        "img_size": img_size,
        "resize": RESIZE,
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
        "metrics": results[chosen_key],
        "evaluation": results,
        "classes": [
            {
                "id": slug,
                "fr": names.get(slug, {}).get("fr", slug.replace("_", " ")),
                "sci": names.get(slug, {}).get("sci") or slug.replace("_", " "),
            }
            for slug in classes  # même ordre que les sorties du modèle
        ],
    }
    (out / "model_card.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nRésultats sur le test :")
    for name, r in results.items():
        extra = f" | accord avec PyTorch {r['agreement_with_pytorch']:.3f}" if "agreement_with_pytorch" in r else ""
        print(f"  {name:10s} accuracy {r['test_acc']:.3f} | top-3 {r['test_top3']:.3f} | macro-F1 {r['macro_f1']:.3f}{extra}")
    print(f"\nFichier retenu : {chosen} ({card['size_mb']} Mo), perte d'accuracy int8 = {drop * 100:.1f} point(s)")
    print(f"Fiche écrite : {out / 'model_card.json'}  ->  étape suivante : python -m src.publish_model --export {out}")


if __name__ == "__main__":
    main()
