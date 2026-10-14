"""
ÉTAPE 3 — Use case 1 : "voici une photo, quel oiseau est-ce ?"

Usage :
    python -m src.predict photo.jpg --ckpt runs/resnet18/best.pt

Affiche les 3 espèces les plus probables avec un pourcentage de confiance.
Le pourcentage vient du softmax : il transforme les scores du modèle en probabilités
qui totalisent 100 %.
"""
import argparse
import json
from pathlib import Path

import torch
from PIL import Image

from src.common import build_model, eval_transform

CONFIDENCE_THRESHOLD = 0.50  # en dessous, on dira "je ne suis pas sûr" -> bascule vers le chat


def load_model(ckpt_path, device="cpu"):
    ckpt = torch.load(ckpt_path, map_location=device)
    model, _ = build_model(ckpt["model"], len(ckpt["classes"]), pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, ckpt["classes"]


@torch.no_grad()
def predict(model, classes, image_path, top_k=3, device="cpu"):
    img = Image.open(image_path).convert("RGB")
    x = eval_transform()(img).unsqueeze(0).to(device)     # (1, 3, 224, 224)
    probs = torch.softmax(model(x), dim=1)[0]
    values, indices = probs.topk(min(top_k, len(classes)))
    return [(classes[i], v.item()) for v, i in zip(values, indices)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--ckpt", default="runs/resnet18/best.pt")
    ap.add_argument("--classes_json", default="data/classes.json")
    args = ap.parse_args()

    model, classes = load_model(args.ckpt)
    names = {}
    if Path(args.classes_json).exists():
        names = {k: v["fr"] for k, v in json.loads(Path(args.classes_json).read_text(encoding="utf-8")).items()}

    results = predict(model, classes, args.image)
    for slug, p in results:
        print(f"{names.get(slug, slug):<28} {p * 100:5.1f} %")
    if results[0][1] < CONFIDENCE_THRESHOLD:
        print("\nJe ne suis pas sûr : on passe en mode chat pour affiner ?")


if __name__ == "__main__":
    main()
