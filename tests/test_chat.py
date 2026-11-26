"""Tests du mode chat avec un modèle factice : pas besoin de scikit-learn ni de modèle entraîné.

Le faux modèle connaît 3 espèces et ne regarde QUE la couleur du dos :
noir -> A, gris -> B, brun -> C. La question la plus utile est donc forcément « couleur_dessus ».
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import chat as chat_mode
from app import config
from app.main import STATS, app, chat_engine_dependency
from src.chat_attributes import ATTRIBUTS, QUESTIONS, VALEURS

ESPECES = ["A", "B", "C"]
COULEUR = {"noir": 0, "gris": 1, "brun": 2}


class FakeModel:
    classes_ = np.array(ESPECES)

    def predict_proba(self, X):
        out = []
        for couleur in X["couleur_dessus"]:
            if couleur in COULEUR:
                p = np.full(3, 0.05)
                p[COULEUR[couleur]] = 0.9
            else:
                p = np.full(3, 1 / 3)
            out.append(p)
        return np.array(out)


def fake_artefact():
    # P(réponse | espèce) : seule la couleur du dos dépend de l'espèce
    freq = {a: {e: {v: 1 / len(VALEURS[a]) for v in VALEURS[a]} for e in ESPECES} for a in ATTRIBUTS}
    for e, couleur in zip(ESPECES, ["noir", "gris", "brun"]):
        freq["couleur_dessus"][e] = {v: (0.92 if v == couleur else 0.02) for v in VALEURS["couleur_dessus"]}
    return {
        "modele": FakeModel(), "attributs": ATTRIBUTS, "valeurs": VALEURS, "questions": QUESTIONS,
        "frequences": freq, "version": "test", "algorithme": "faux",
        "especes": [{"id": e, "fr": f"Oiseau {e}", "sci": f"Avis {e.lower()}"} for e in ESPECES],
    }


@pytest.fixture
def client():
    engine = chat_mode.ChatEngine(fake_artefact())
    app.dependency_overrides[chat_engine_dependency] = lambda: engine
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_questions_lists_the_12_attributes(client):
    body = client.get("/chat/questions").json()
    assert [q["attribut"] for q in body] == ATTRIBUTS
    assert all("je ne sais pas" in q["choix"] for q in body)


def test_first_turn_asks_the_most_informative_question(client):
    response = client.post("/chat", json={"reponses": {}})
    assert response.status_code == 200
    body = response.json()
    assert body["termine"] is False
    assert body["question_suivante"]["attribut"] == "couleur_dessus"
    assert len(body["predictions"]) == 3
    assert body["gains"]["couleur_dessus"] > body["gains"]["taille"]


def test_confident_answer_ends_the_chat(client):
    body = client.post("/chat", json={"reponses": {"couleur_dessus": "gris"}}).json()
    assert body["predictions"][0]["species_id"] == "B"
    assert body["predictions"][0]["confidence"] == 0.9
    assert body["termine"] is True
    assert body["question_suivante"] is None
    assert body["nb_reponses"] == 1


def test_je_ne_sais_pas_is_accepted_and_not_asked_again(client):
    body = client.post("/chat", json={"reponses": {"couleur_dessus": "je ne sais pas"}}).json()
    assert body["nb_reponses"] == 0
    assert "couleur_dessus" not in body["gains"]
    # plus rien d'utile à demander au faux modèle : il s'arrête plutôt que de poser des questions inutiles
    assert body["termine"] is True


def test_unknown_attribute_is_rejected(client):
    response = client.post("/chat", json={"reponses": {"couleur_des_pattes": "rose"}})
    assert response.status_code == 400
    assert "Question inconnue" in response.json()["detail"]


def test_unknown_value_is_rejected_with_choices(client):
    response = client.post("/chat", json={"reponses": {"couleur_dessus": "violet"}})
    assert response.status_code == 400
    assert "noir" in response.json()["detail"]


def test_chat_requests_are_counted(client):
    before = STATS["chat_requests"]
    client.post("/chat", json={"reponses": {}})
    assert client.get("/stats").json()["chat_requests"] == before + 1


def test_missing_chat_model_gives_503(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CHAT_MODEL_PATH_EUROPE", tmp_path / "absent.joblib")
    chat_mode.get_engine.cache_clear()
    response = TestClient(app).post("/chat?region=europe", json={"reponses": {}})
    assert response.status_code == 503
    assert "notebook 03" in response.json()["detail"]
