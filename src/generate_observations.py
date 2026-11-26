"""BirdsFinder — Bloc 03 : générateur d'observations simulées.

Lit les fiches espèces (export CSV du tableau « Fiches ») et fabrique des
observations « comme un vrai utilisateur » : avec des erreurs de perception,
quelques erreurs franches et des réponses « je ne sais pas » (valeurs vides).

Usage (depuis la racine du dépôt) :
    python -m src.generate_observations --fiches data/bloc03/profils_especes.csv \
        --out data/bloc03/observations_simulees.csv --per-species 300 --seed 42
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.chat_attributes import (
    ATTRIBUTS,
    COLONNES_FICHES,
    ORDINAUX,
    VALEURS,
    decouper_nom,
)

# Erreurs de perception : les confusions « proches » qu'un humain fait
VOISINS_COULEUR = {
    "noir": ["gris", "brun"],
    "gris": ["noir", "blanc", "brun"],
    "brun": ["noir", "gris"],
    "blanc": ["gris"],
    "vert": ["gris", "noir"],
    "jaune": ["blanc", "orange/rouge"],
    "orange/rouge": ["jaune", "brun"],
}
VOISINS_AUTRES = {
    "fin droit": ["fin courbé"], "fin courbé": ["fin droit"],
    "gros conique": ["fin droit"], "long pointu": ["fin droit"],
    "clair": ["sombre"], "sombre": ["clair"],
    "sourcil marqué": ["aucune"], "masque sombre": ["aucune"],
    "tache sur le cou": ["aucune"], "tache rousse": ["aucune"],
    "jardin/ville": ["prairie/champ"], "prairie/champ": ["jardin/ville"],
    "forêt": ["jardin/ville"], "bord de l'eau": ["prairie/champ"],
    "au sol": ["dans la végétation"], "dans la végétation": ["au sol", "perché (fil ou branche)"],
    "perché (fil ou branche)": ["dans la végétation"],
}

# Hypothèses du générateur (à présenter comme telles au jury)
P_PERCEPTION = 0.10   # valeur voisine
P_ALEATOIRE = 0.03    # valeur au hasard
P_MANQUANT = {        # « je ne sais pas » : plus fréquent pour les détails fins
    "taille": 0.25, "couleur_dessus": 0.20, "couleur_dessous": 0.25,
    "tache_vive": 0.35, "forme_bec": 0.45, "longueur_bec": 0.45,
    "couleur_bec": 0.50, "oeil": 0.55, "queue": 0.45, "marque_tete": 0.45,
    "activite": 0.30, "milieu": 0.30,
}
MIN_REPONSES = 2      # une description contient au moins 2 réponses


def lire_fiches(chemin: str) -> pd.DataFrame:
    """Lit l'export du tableau, même s'il contient les lignes de consignes au-dessus de l'en-tête."""
    brut = pd.read_csv(chemin, header=None, dtype=str)
    ligne_entete = brut.index[brut.iloc[:, 0].fillna("").str.strip() == "Espèce"][0]
    fiches = pd.read_csv(chemin, skiprows=ligne_entete, dtype=str)
    fiches = fiches.dropna(subset=["Espèce"]).rename(columns=COLONNES_FICHES)
    fiches["Espèce"] = fiches["Espèce"].str.strip()
    manquantes = [a for a in ATTRIBUTS if a not in fiches.columns]
    if manquantes:
        raise ValueError(f"Colonnes absentes du fichier : {manquantes}")
    for a in ATTRIBUTS:  # contrôle : toute valeur de fiche doit être une réponse possible
        inconnues = set(fiches[a].dropna()) - set(VALEURS[a])
        if inconnues:
            raise ValueError(f"{a} : valeurs inconnues {inconnues} (à ajouter dans src/chat_attributes.py)")
    ids = fiches["Espèce"].map(lambda e: decouper_nom(e)[0])
    fiches.insert(0, "espece_id", ids)
    fiches.insert(1, "nom_fr", fiches["Espèce"].map(lambda e: decouper_nom(e)[1]))
    fiches.insert(2, "nom_sci", fiches["Espèce"].map(lambda e: decouper_nom(e)[2]))
    return fiches


def perturber(attribut: str, valeur: str, rng: np.random.Generator) -> str:
    """Applique (ou non) une erreur de perception ou une erreur franche."""
    tirage = rng.random()
    if tirage < P_ALEATOIRE:
        autres = [v for v in VALEURS[attribut] if v != valeur]
        return str(rng.choice(autres))
    if tirage < P_ALEATOIRE + P_PERCEPTION:
        if attribut in ORDINAUX:
            i = VALEURS[attribut].index(valeur)
            voisins = [VALEURS[attribut][j] for j in (i - 1, i + 1) if 0 <= j < len(VALEURS[attribut])]
        else:
            table = VOISINS_COULEUR if attribut.startswith("couleur") else VOISINS_AUTRES
            voisins = [v for v in table.get(valeur, []) if v in VALEURS[attribut]]
        if voisins:
            return str(rng.choice(voisins))
    return valeur


def generer(fiches: pd.DataFrame, par_espece: int = 300, graine: int = 42) -> pd.DataFrame:
    """par_espece observations par espèce ; mâle/femelle tirés au hasard quand il y a 2 fiches."""
    rng = np.random.default_rng(graine)
    lignes = []
    for espece_id, variantes in fiches.groupby("espece_id", sort=False):
        for _ in range(par_espece):
            fiche = variantes.iloc[rng.integers(len(variantes))]
            obs = {"espece_id": espece_id, "nom_fr": fiche["nom_fr"], "variante": fiche["Variante"]}
            for a in ATTRIBUTS:
                vraie = fiche[a]
                obs[a] = None if pd.isna(vraie) or rng.random() < P_MANQUANT[a] else perturber(a, vraie, rng)
            # au moins MIN_REPONSES réponses : on rétablit des attributs au hasard
            vides = [a for a in ATTRIBUTS if obs[a] is None and pd.notna(fiche[a])]
            while sum(obs[a] is not None for a in ATTRIBUTS) < MIN_REPONSES and vides:
                a = vides.pop(int(rng.integers(len(vides))))
                obs[a] = fiche[a]
            lignes.append(obs)
    df = pd.DataFrame(lignes)
    df.insert(0, "id", range(1, len(df) + 1))
    return df


def main() -> None:
    p = argparse.ArgumentParser(description="Génère les observations simulées du mode chat (Bloc 03).")
    p.add_argument("--fiches", default="data/bloc03/profils_especes.csv")
    p.add_argument("--out", default="data/bloc03/observations_simulees.csv")
    p.add_argument("--per-species", type=int, default=300)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    fiches = lire_fiches(args.fiches)
    obs = generer(fiches, args.per_species, args.seed)
    obs.to_csv(args.out, index=False)

    print(f"{len(fiches)} fiches, {fiches['espece_id'].nunique()} espèces -> {len(obs)} observations : {args.out}")
    print("\nTaux de « je ne sais pas » par attribut :")
    print(obs[ATTRIBUTS].isna().mean().round(2).to_string())
    print(f"\nRéponses par observation : moyenne {obs[ATTRIBUTS].notna().sum(axis=1).mean():.1f} sur {len(ATTRIBUTS)}")


if __name__ == "__main__":
    main()
