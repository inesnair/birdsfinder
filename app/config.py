"""Réglages de l'API, modifiables par variables d'environnement (utile avec Docker)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = Path(os.getenv("MODEL_PATH", BASE_DIR / "models" / "best.pt"))
CLASSES_JSON = Path(os.getenv("CLASSES_JSON", BASE_DIR / "data" / "classes.json"))

TOP_K = int(os.getenv("TOP_K", "3"))                                   # nb d'espèces renvoyées
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))  # en dessous : "pas sûr"
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
