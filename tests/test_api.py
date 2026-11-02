"""Tests de l'API avec un prédicteur factice : pas besoin de torch ni de modèle entraîné."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import config, inference
from app.inference import Prediction
from app.main import STATS, app, predictor_dependency


class FakePredictor:
    def __init__(self, top_confidence: float):
        self.top = top_confidence

    def predict(self, image, top_k):
        rest = (1 - self.top) / 2
        return [
            Prediction("mesange_bleue", "Mésange bleue", "Cyanistes caeruleus", self.top),
            Prediction("mesange_noire", "Mésange noire", "Periparus ater", rest),
            Prediction("mesange_nonnette", "Mésange nonnette", "Poecile palustris", rest),
        ][:top_k]


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (30, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_fake(confidence: float):
    app.dependency_overrides[predictor_dependency] = lambda: FakePredictor(confidence)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_confident(client):
    use_fake(0.9)
    response = client.post("/predict/image", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert len(body["predictions"]) == 3
    assert body["predictions"][0]["name_fr"] == "Mésange bleue"
    assert body["predictions"][0]["confidence"] == 0.9
    assert body["uncertain"] is False
    assert body["suggestion"] is None


def test_predict_uncertain_suggests_chat(client):
    use_fake(0.3)
    response = client.post("/predict/image", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    body = response.json()
    assert body["uncertain"] is True
    assert "chat" in body["suggestion"]


def test_rejects_non_image(client):
    use_fake(0.9)
    response = client.post("/predict/image", files={"file": ("note.txt", b"bonjour", "text/plain")})
    assert response.status_code == 400


def test_rejects_corrupted_image(client):
    use_fake(0.9)
    response = client.post("/predict/image", files={"file": ("faux.png", b"pas une image", "image/png")})
    assert response.status_code == 400


def test_returns_503_when_model_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MODEL_PATH", tmp_path / "absent.pt")
    inference.get_predictor.cache_clear()
    response = client.post("/predict/image", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert response.status_code == 503
    assert "Modèle introuvable" in response.json()["detail"]


def test_stats_count_requests(client):
    use_fake(0.9)
    before = STATS["image_requests"]
    client.post("/predict/image", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert client.get("/stats").json()["image_requests"] == before + 1


def test_response_contains_default_region(client):
    use_fake(0.9)
    response = client.post("/predict/image", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert response.json()["region"] == config.DEFAULT_REGION


def test_predict_with_europe_region(client):
    use_fake(0.9)
    response = client.post("/predict/image?region=europe", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert response.status_code == 200
    assert response.json()["region"] == "europe"
    assert STATS["by_region"]["europe"] >= 1


def test_unknown_region_is_rejected(client):
    use_fake(0.9)
    response = client.post("/predict/image?region=mars", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert response.status_code == 400
    assert "Zone inconnue" in response.json()["detail"]


def test_europe_model_missing_gives_503_but_antilles_unaffected(client, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "MODEL_PATH_EUROPE", tmp_path / "absent_europe.pt")
    inference.get_predictor.cache_clear()
    response = client.post("/predict/image?region=europe", files={"file": ("oiseau.png", png_bytes(), "image/png")})
    assert response.status_code == 503
    assert "absent_europe.pt" in response.json()["detail"]


def test_regions_lists_availability(client, monkeypatch, tmp_path):
    present = tmp_path / "antilles.pt"
    present.write_bytes(b"x")
    monkeypatch.setattr(config, "MODEL_PATH", present)
    monkeypatch.setattr(config, "MODEL_PATH_EUROPE", tmp_path / "absent.pt")
    body = {r["id"]: r for r in client.get("/regions").json()}
    assert body["antilles"]["model_file_found"] is True
    assert body["europe"]["model_file_found"] is False
    assert sum(r["default"] for r in body.values()) == 1


def test_chat_not_implemented_yet(client):
    response = client.post("/chat", json={"message": "j'ai vu un oiseau bleu"})
    assert response.status_code == 501
