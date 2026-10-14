"""
Chargement du modèle entraîné + prédiction.

torch n'est importé qu'à la demande : l'API démarre (et les tests tournent) même sans
torch ni modèle entraîné. /predict/image répond alors 503 avec un message explicite.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image

from app import config


class ModelNotAvailable(RuntimeError):
    """Le fichier du modèle est absent ou illisible."""


@dataclass
class Prediction:
    species_id: str
    name_fr: str
    scientific_name: str | None
    confidence: float


class ImagePredictor:
    """Enveloppe un CNN fine-tuné : image PIL -> top-k espèces avec confiance (softmax)."""

    def __init__(self, model_path: Path, classes_json: Path | None = None, device: str = "cpu"):
        import torch

        from src.common import build_model, eval_transform

        self._torch = torch
        self.device = device
        ckpt = torch.load(model_path, map_location=device)
        self.classes: list[str] = ckpt["classes"]
        model, _ = build_model(ckpt["model"], len(self.classes), pretrained=False)
        model.load_state_dict(ckpt["state_dict"])
        self.model = model.to(device).eval()
        self.transform = eval_transform()  # exactement le même prétraitement qu'à l'entraînement
        self.names: dict[str, dict] = {}
        if classes_json and Path(classes_json).exists():
            self.names = json.loads(Path(classes_json).read_text(encoding="utf-8"))

    def predict(self, image: Image.Image, top_k: int = 3) -> list[Prediction]:
        torch = self._torch
        x = self.transform(image.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)[0]
        values, indices = probs.topk(min(top_k, len(self.classes)))
        results = []
        for value, idx in zip(values.tolist(), indices.tolist()):
            slug = self.classes[idx]
            info = self.names.get(slug, {})
            results.append(Prediction(slug, info.get("fr", slug), info.get("sci"), value))
        return results


@lru_cache(maxsize=1)
def get_predictor() -> ImagePredictor:
    """Charge le modèle une seule fois (au premier appel), puis le garde en mémoire."""
    if not config.MODEL_PATH.exists():
        raise ModelNotAvailable(
            f"Modèle introuvable : {config.MODEL_PATH}. Voir le README, section « Modèle »."
        )
    try:
        return ImagePredictor(config.MODEL_PATH, config.CLASSES_JSON)
    except Exception as exc:  # fichier corrompu, pointeur Git LFS non téléchargé, torch absent...
        raise ModelNotAvailable(
            f"Impossible de charger le modèle ({exc}). Vérifie Git LFS et l'installation de torch."
        ) from exc
