"""Test du vrai chargement de modèle avec un mini-checkpoint. Ignoré si torch n'est pas installé."""
import json

import pytest
from PIL import Image

torch = pytest.importorskip("torch")
pytest.importorskip("torchvision")

from app.inference import ImagePredictor  # noqa: E402
from src.common import build_model  # noqa: E402


def test_predictor_loads_checkpoint_and_predicts(tmp_path):
    classes = ["mesange_bleue", "merle_noir", "pie_bavarde"]
    model, _ = build_model("resnet18", len(classes), pretrained=False)
    ckpt_path = tmp_path / "best.pt"
    torch.save({"state_dict": model.state_dict(), "classes": classes, "model": "resnet18", "img_size": 224}, ckpt_path)
    classes_json = tmp_path / "classes.json"
    classes_json.write_text(json.dumps({"merle_noir": {"fr": "Merle noir", "sci": "Turdus merula"}}), encoding="utf-8")

    predictor = ImagePredictor(ckpt_path, classes_json)
    results = predictor.predict(Image.new("RGB", (300, 200), (10, 10, 10)), top_k=3)

    assert len(results) == 3
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)
    assert sum(confidences) == pytest.approx(1.0, abs=1e-3)
    assert {r.species_id for r in results} == set(classes)
