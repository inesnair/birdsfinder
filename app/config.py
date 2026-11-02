"""Réglages de l'API, modifiables par variables d'environnement (utile avec Docker)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Modèle Antilles (nommage historique conservé : models/best.pt + data/classes.json)
MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "models" / "best.pt"))
CLASSES_JSON = Path(os.getenv("CLASSES_JSON", BASE_DIR / "data" / "classes.json"))

# Modèle Europe (France métropolitaine)
MODEL_PATH_EUROPE = Path(os.getenv("MODEL_PATH_EUROPE", BASE_DIR / "models" / "best_europe.pt"))
CLASSES_JSON_EUROPE = Path(os.getenv("CLASSES_JSON_EUROPE", BASE_DIR / "data" / "classes_europe.json"))

# Zones proposées : identifiant -> libellé affiché dans l'interface
REGION_LABELS = {
    "antilles": "Antilles françaises",
    "europe": "Europe (France métropolitaine)",
}
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "antilles")

TOP_K = int(os.getenv("TOP_K", "3"))                                   # nb d'espèces renvoyées
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))  # en dessous : "pas sûr"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))


def region_files(region: str) -> tuple[Path, Path]:
    """(fichier modèle, fichier classes.json) d'une zone. Lu à chaque appel (utile pour les tests)."""
    if region == "europe":
        return MODEL_PATH_EUROPE, CLASSES_JSON_EUROPE
    if region == "antilles":
        return MODEL_PATH, CLASSES_JSON
    raise KeyError(region)
