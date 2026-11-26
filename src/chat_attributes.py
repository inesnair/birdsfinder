"""Mode chat (Bloc 03) : les 12 questions et leurs réponses possibles.

Source unique de vérité, partagée par :
  - src/generate_observations.py (fabrication des données simulées),
  - src/chat_model.py et le notebook 03 (entraînement),
  - app/chat.py (l'API : validation des réponses et choix de la question suivante).

Pur Python (aucune dépendance) : l'API et la CI peuvent l'importer sans scikit-learn.
"""
import re

# Colonne du tableau « Fiches espèces » -> nom court de l'attribut
COLONNES_FICHES = {
    "Taille (bec → queue)": "taille",
    "Couleur du dos": "couleur_dessus",
    "Couleur du ventre": "couleur_dessous",
    "Tache vive": "tache_vive",
    "Forme du bec": "forme_bec",
    "Longueur du bec (comparée à la tête)": "longueur_bec",
    "Couleur du bec": "couleur_bec",
    "Œil": "oeil",
    "Queue": "queue",
    "Marque sur la tête": "marque_tete",
    "Que faisait-il ?": "activite",
    "Où ?": "milieu",
}
ATTRIBUTS = list(COLONNES_FICHES.values())

# Texte de la question posée à l'utilisateur
QUESTIONS = {
    "taille": "Quelle taille fait-il, du bout du bec au bout de la queue ?",
    "couleur_dessus": "De quelle couleur est son dos ?",
    "couleur_dessous": "De quelle couleur est son ventre ?",
    "tache_vive": "As-tu vu une tache de couleur vive ?",
    "forme_bec": "Quelle forme a son bec ?",
    "longueur_bec": "Son bec est-il court, moyen ou long (comparé à sa tête) ?",
    "couleur_bec": "De quelle couleur est son bec ?",
    "oeil": "Son œil est-il clair ou sombre ?",
    "queue": "Sa queue est-elle courte, normale ou longue ?",
    "marque_tete": "As-tu remarqué une marque sur la tête ou le cou ?",
    "activite": "Que faisait-il ?",
    "milieu": "Où l'as-tu vu ?",
}

# Réponses possibles (= listes déroulantes du tableau). L'ordre compte pour les ordinaux.
VALEURS = {
    "taille": ["< 10 cm (colibri)", "10–20 cm (moineau)", "20–40 cm (merle, pigeon)", "> 40 cm (héron)"],
    "couleur_dessus": ["noir", "gris", "brun", "vert", "blanc"],
    "couleur_dessous": ["noir", "gris", "blanc", "jaune", "brun", "vert"],
    "tache_vive": ["aucune", "gorge rouge/rousse", "gorge pourpre", "ventre jaune",
                   "huppe brillante", "cou irisé", "houpette orange"],
    "forme_bec": ["fin droit", "fin courbé", "gros conique", "long pointu"],
    "longueur_bec": ["court", "moyen", "long"],
    "couleur_bec": ["noir", "gris", "jaune", "orange/rouge"],
    "oeil": ["clair", "sombre"],
    "queue": ["courte", "normale", "longue"],
    "marque_tete": ["aucune", "sourcil marqué", "masque sombre", "visage noir",
                    "tache sur le cou", "tache rousse"],
    "activite": ["au sol", "perché (fil ou branche)", "devant des fleurs",
                 "près du bétail", "dans la végétation"],
    "milieu": ["jardin/ville", "prairie/champ", "forêt", "bord de l'eau"],
}

# Attributs dont les valeurs ont un ordre (on peut se tromper « d'un cran »)
ORDINAUX = ("taille", "longueur_bec", "queue")

JE_NE_SAIS_PAS = "je ne sais pas"


def slug(text: str) -> str:
    """Même règle que build_antilles_dataset.py : « Quiscalus lugubris » -> « Quiscalus_lugubris »."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def decouper_nom(espece: str) -> tuple[str, str, str]:
    """« Quiscale merle (Quiscalus lugubris) » -> (id, nom français, nom scientifique)."""
    m = re.match(r"^\s*(.+?)\s*\((.+)\)\s*$", espece)
    if not m:
        raise ValueError(f"Nom d'espèce attendu sous la forme « Nom français (Nom scientifique) » : {espece!r}")
    fr, sci = m.group(1), m.group(2)
    return slug(sci), fr, sci
