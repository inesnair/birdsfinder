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

# Front React compilé (frontend/dist) : servi par l'API s'il existe (démo Colab / local)
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", BASE_DIR / "frontend" / "dist"))
# Origines autorisées à appeler l'API depuis un autre site (ex. "https://inesnair.github.io"), séparées par des virgules
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
MODEL_VERSION = os.getenv("MODEL_VERSION", "api-locale")

TOP_K = int(os.getenv("TOP_K", "3"))                                   # nb d'espèces renvoyées
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))  # en dessous : "pas sûr"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

# Mode chat (Bloc 03) : un modèle scikit-learn par zone, entraîné dans le notebook 03
CHAT_MODEL_PATH = Path(os.getenv("CHAT_MODEL_PATH", BASE_DIR / "models" / "chat_antilles.joblib"))
CHAT_MODEL_PATH_EUROPE = Path(os.getenv("CHAT_MODEL_PATH_EUROPE", BASE_DIR / "models" / "chat_europe.joblib"))
CHAT_STOP_THRESHOLD = float(os.getenv("CHAT_STOP_THRESHOLD", "0.8"))  # 1re espèce assez sûre : on s'arrête
CHAT_MIN_GAIN = float(os.getenv("CHAT_MIN_GAIN", "0.02"))  # gain d'information minimal pour poser une question


def region_files(region: str) -> tuple[Path, Path]:
    """(fichier modèle, fichier classes.json) d'une zone. Lu à chaque appel (utile pour les tests)."""
    if region == "europe":
        return MODEL_PATH_EUROPE, CLASSES_JSON_EUROPE
    if region == "antilles":
        return MODEL_PATH, CLASSES_JSON
    raise KeyError(region)


def chat_model_file(region: str) -> Path:
    """Fichier du modèle de chat d'une zone. Lu à chaque appel (utile pour les tests)."""
    if region == "europe":
        return CHAT_MODEL_PATH_EUROPE
    if region == "antilles":
        return CHAT_MODEL_PATH
    raise KeyError(region)
