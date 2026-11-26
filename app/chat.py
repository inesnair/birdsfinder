"""Mode chat (Bloc 03) : identifier un oiseau à partir de réponses à des questions.

Le modèle (entraîné dans le notebook 03) est chargé depuis models/chat_<zone>.joblib.
À chaque appel, l'API :
  1. prédit les espèces les plus probables à partir des réponses déjà données ;
  2. choisit la question suivante : celle dont la réponse devrait le plus réduire
     l'incertitude (gain d'information = baisse attendue de l'entropie) ;
  3. s'arrête quand la 1re espèce est assez sûre, ou quand plus aucune question n'aide.

Aucun état n'est gardé côté serveur : le client renvoie toutes ses réponses à chaque tour.
scikit-learn et joblib ne sont importés qu'au chargement du modèle (la CI s'en passe).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from app import config
from src.chat_attributes import JE_NE_SAIS_PAS


class ChatModelNotAvailable(RuntimeError):
    """Le fichier du modèle de chat est absent ou illisible."""


class InvalidAnswer(ValueError):
    """Attribut inconnu ou réponse hors liste."""


@dataclass
class ChatResult:
    predictions: list[tuple[dict, float]]          # (espèce, probabilité), par probabilité décroissante
    question: str | None                           # attribut à demander ensuite (None = fini)
    gains: dict[str, float] = field(default_factory=dict)  # gain d'information de chaque question candidate
    termine: bool = False
    nb_reponses: int = 0


def entropie(p: np.ndarray) -> float:
    """Incertitude d'une distribution (en bits) : 0 = certain, log2(10) ≈ 3,3 = 10 espèces à égalité."""
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


class ChatEngine:
    def __init__(self, artefact: dict):
        self.modele = artefact["modele"]
        self.attributs: list[str] = artefact["attributs"]
        self.valeurs: dict[str, list[str]] = artefact["valeurs"]
        self.questions: dict[str, str] = artefact["questions"]
        self.frequences: dict = artefact["frequences"]
        self.version: str = artefact.get("version", "?")
        self.algorithme: str = artefact.get("algorithme", "?")
        self.classes: list[str] = list(self.modele.classes_)
        especes = {e["id"]: e for e in artefact["especes"]}
        self.especes = [especes.get(c, {"id": c, "fr": c, "sci": None}) for c in self.classes]

    # ---------- validation ----------
    def nettoyer(self, reponses: dict[str, str]) -> tuple[dict[str, str], set[str]]:
        """-> (réponses utiles, attributs déjà posés). « je ne sais pas » compte comme posé mais vide."""
        utiles, posees = {}, set()
        for attribut, valeur in reponses.items():
            if attribut not in self.valeurs:
                raise InvalidAnswer(f"Question inconnue : « {attribut} ». Questions : {', '.join(self.attributs)}.")
            valeur = (valeur or "").strip()
            posees.add(attribut)
            if valeur.lower() == JE_NE_SAIS_PAS:
                continue
            if valeur not in self.valeurs[attribut]:
                choix = " · ".join(self.valeurs[attribut] + [JE_NE_SAIS_PAS])
                raise InvalidAnswer(f"Réponse « {valeur} » impossible pour « {attribut} ». Choix : {choix}.")
            utiles[attribut] = valeur
        return utiles, posees

    # ---------- prédiction ----------
    def _probas(self, lignes: list[dict[str, str]]) -> np.ndarray:
        X = pd.DataFrame(lignes, columns=self.attributs).astype(object)
        X = X.where(X.notna(), np.nan)
        return np.asarray(self.modele.predict_proba(X))

    def _gain(self, attribut: str, reponses: dict[str, str], p: np.ndarray) -> float:
        """Baisse d'entropie attendue si l'on pose cette question."""
        valeurs = self.valeurs[attribut]
        # P(réponse) = somme sur les espèces de P(espèce) × P(réponse | espèce)
        p_reponse = np.array([
            sum(p[i] * self.frequences[attribut][c][v] for i, c in enumerate(self.classes)) for v in valeurs
        ])
        p_reponse = p_reponse / p_reponse.sum()
        apres = self._probas([{**reponses, attribut: v} for v in valeurs])
        attendue = sum(pv * entropie(post) for pv, post in zip(p_reponse, apres))
        return entropie(p) - attendue

    def tour(self, reponses: dict[str, str], seuil: float | None = None, gain_min: float | None = None) -> ChatResult:
        seuil = config.CHAT_STOP_THRESHOLD if seuil is None else seuil
        gain_min = config.CHAT_MIN_GAIN if gain_min is None else gain_min
        utiles, posees = self.nettoyer(reponses)
        p = self._probas([utiles])[0]
        ordre = np.argsort(p)[::-1]
        predictions = [(self.especes[i], float(p[i])) for i in ordre]

        gains = {}
        if p[ordre[0]] < seuil:
            gains = {a: round(self._gain(a, utiles, p), 4) for a in self.attributs if a not in posees}
        meilleure = max(gains, key=gains.get) if gains else None
        if meilleure is not None and gains[meilleure] < gain_min:
            meilleure = None
        return ChatResult(predictions=predictions, question=meilleure, gains=gains,
                          termine=meilleure is None, nb_reponses=len(utiles))


@lru_cache(maxsize=4)
def get_engine(region: str) -> ChatEngine:
    """Charge (une seule fois) le modèle de chat d'une zone."""
    chemin = config.chat_model_file(region)
    if not chemin.exists():
        raise ChatModelNotAvailable(
            f"Modèle de chat introuvable pour la zone « {region} » : {chemin}. "
            "Entraîne-le avec le notebook 03 puis copie chat_<zone>.joblib dans models/."
        )
    try:
        import joblib

        return ChatEngine(joblib.load(chemin))
    except Exception as exc:  # fichier corrompu, version de scikit-learn incompatible...
        raise ChatModelNotAvailable(f"Modèle de chat illisible ({chemin.name}) : {exc}") from exc


def phrase(result: ChatResult) -> str:
    """Petit message lisible pour la démo."""
    espece, p = result.predictions[0]
    pct = round(p * 100)
    if result.termine:
        return f"C'est probablement un(e) {espece['fr']} ({pct} %)."
    return f"Pour l'instant je pense à {espece['fr']} ({pct} %). Une question pour affiner :"
