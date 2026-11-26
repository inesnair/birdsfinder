"""Mode chat (Bloc 03) : préparation des données, les 5 algorithmes comparés, métriques et sauvegarde.

Utilisé par le notebook 03. Chaque algorithme est un Pipeline scikit-learn complet
(prétraitement + modèle) qui prend directement un DataFrame des 12 attributs,
avec NaN pour « je ne sais pas » : c'est ce même objet que l'API charge.
"""
from __future__ import annotations

from datetime import date

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    make_scorer,
    top_k_accuracy_score,
)
from sklearn.naive_bayes import CategoricalNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

from src.chat_attributes import ATTRIBUTS, JE_NE_SAIS_PAS, ORDINAUX, QUESTIONS, VALEURS

INCONNU = "inconnu"
GRAINE = 42


# ---------- 1) Données : du tableau aux colonnes que le modèle lit ----------
def preparer_X(df: pd.DataFrame) -> pd.DataFrame:
    """Les 12 attributs, en texte, avec NaN pour toute réponse absente ou « je ne sais pas »."""
    X = df.reindex(columns=ATTRIBUTS).astype(object)
    X = X.where(X.notna() & (X != JE_NE_SAIS_PAS) & (X != ""), np.nan)
    return X


# ---------- 2) Les 5 algorithmes (prétraitement adapté à chacun) ----------
def _one_hot() -> Pipeline:
    """« je ne sais pas » -> ligne de zéros : le modèle n'apprend rien de cette case."""
    return Pipeline([
        ("trou", SimpleImputer(strategy="constant", fill_value=INCONNU)),
        ("onehot", OneHotEncoder(categories=[VALEURS[a] for a in ATTRIBUTS], handle_unknown="ignore")),
    ])


def construire_modeles() -> dict[str, Pipeline]:
    """Nom lisible -> Pipeline non entraîné."""
    nb_categories = [len(VALEURS[a]) + 1 for a in ATTRIBUTS]  # +1 pour « inconnu »
    return {
        "Référence (proportions)": Pipeline([
            ("modele", DummyClassifier(strategy="prior")),
        ]),
        "Naive Bayes catégoriel": Pipeline([
            ("trou", SimpleImputer(strategy="constant", fill_value=INCONNU)),
            ("code", OrdinalEncoder(categories=[VALEURS[a] + [INCONNU] for a in ATTRIBUTS],
                                    handle_unknown="use_encoded_value", unknown_value=-1)),
            ("modele", CategoricalNB(alpha=1.0, min_categories=nb_categories)),
        ]),
        "Régression logistique": Pipeline([
            ("prep", _one_hot()),
            ("modele", LogisticRegression(C=1.0, max_iter=2000)),
        ]),
        "Random Forest": Pipeline([
            ("prep", _one_hot()),
            ("modele", RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=GRAINE, n_jobs=-1)),
        ]),
        "HistGradientBoosting": Pipeline([
            ("code", ColumnTransformer([(
                "ordinal",
                OrdinalEncoder(categories=[VALEURS[a] for a in ATTRIBUTS], handle_unknown="use_encoded_value",
                               unknown_value=np.nan, encoded_missing_value=np.nan),
                ATTRIBUTS,
            )])),
            # NaN gérés nativement ; les attributs non ordonnés sont déclarés catégoriels
            ("modele", HistGradientBoostingClassifier(
                categorical_features=[a not in ORDINAUX for a in ATTRIBUTS],
                learning_rate=0.1, max_iter=200, random_state=GRAINE)),
        ]),
    }


# ---------- 3) Indicateurs de succès ----------
def scorers(classes: list[str]) -> dict:
    """Pour cross_validate : accuracy, top-3, macro-F1, log-loss (la loss optimisée)."""
    return {
        "accuracy": "accuracy",
        "top3": make_scorer(top_k_accuracy_score, response_method="predict_proba", k=3, labels=classes),
        "f1_macro": "f1_macro",
        "log_loss": make_scorer(log_loss, response_method="predict_proba", greater_is_better=False,
                                labels=classes),
    }


def evaluer(modele, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    """Les 4 indicateurs sur un jeu de données (ex. : le test humain)."""
    classes = list(modele.classes_)
    proba = modele.predict_proba(X)
    pred = np.asarray(classes)[proba.argmax(axis=1)]
    return {
        "accuracy": accuracy_score(y, pred),
        "top3": top_k_accuracy_score(y, proba, k=3, labels=classes),
        "f1_macro": f1_score(y, pred, average="macro", labels=classes, zero_division=0),
        "log_loss": log_loss(y, proba, labels=classes),
    }


# ---------- 4) Ce dont l'API a besoin pour choisir la question suivante ----------
def frequences_reponses(obs: pd.DataFrame, alpha: float = 1.0) -> dict:
    """P(réponse | espèce) pour chaque attribut, estimée sur les observations (lissage de Laplace).

    Sert à l'API pour prévoir « quelle réponse l'utilisateur va probablement donner »
    et calculer le gain d'information de chaque question.
    """
    freq: dict = {}
    for a in ATTRIBUTS:
        freq[a] = {}
        for espece, groupe in obs.groupby("espece_id"):
            comptes = groupe[a].value_counts()
            total = comptes.sum() + alpha * len(VALEURS[a])
            freq[a][espece] = {v: float((comptes.get(v, 0) + alpha) / total) for v in VALEURS[a]}
    return freq


def sauver_artefact(chemin, modele, nom_algo: str, obs: pd.DataFrame, fiches: pd.DataFrame,
                    metriques: dict, region: str = "antilles") -> dict:
    """Tout ce que l'API charge, dans un seul fichier .joblib."""
    especes = (fiches[["espece_id", "nom_fr", "nom_sci"]].drop_duplicates("espece_id")
               .rename(columns={"espece_id": "id", "nom_fr": "fr", "nom_sci": "sci"}).to_dict("records"))
    artefact = {
        "region": region,
        "version": f"chat-{region}-{date.today().isoformat()}",
        "algorithme": nom_algo,
        "modele": modele,
        "attributs": ATTRIBUTS,
        "valeurs": VALEURS,
        "questions": QUESTIONS,
        "especes": especes,
        "frequences": frequences_reponses(obs),
        "metriques": metriques,
    }
    joblib.dump(artefact, chemin)
    return artefact
