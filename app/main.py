"""API BirdsFinder (FastAPI) : identification d'oiseaux par photo (et bientôt par chat)."""
import io
import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from app import config, inference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("birdsfinder")

app = FastAPI(
    title="BirdsFinder",
    version="0.1.0",
    description="Identifie un oiseau à partir d'une photo (deep learning) ou d'une description (chat).",
)

STATIC_DIR = Path(__file__).parent / "static"

# Compteurs simples pour le monitoring (consultables sur /stats).
STATS = {"image_requests": 0, "uncertain": 0, "total_latency_ms": 0.0}


# ---------- Schémas (contrat de l'API) ----------
class SpeciesScore(BaseModel):
    species_id: str
    name_fr: str
    scientific_name: str | None = None
    confidence: float  # entre 0 et 1


class ImagePredictionResponse(BaseModel):
    predictions: list[SpeciesScore]
    uncertain: bool
    suggestion: str | None = None


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


# ---------- Dépendance : le modèle (remplaçable dans les tests) ----------
def predictor_dependency():
    try:
        return inference.get_predictor()
    except inference.ModelNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---------- Routes ----------
@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model_file_found": config.MODEL_PATH.exists()}


@app.get("/stats")
def stats():
    n = STATS["image_requests"]
    return {
        "image_requests": n,
        "uncertain_predictions": STATS["uncertain"],
        "avg_latency_ms": round(STATS["total_latency_ms"] / n, 1) if n else None,
    }


@app.post("/predict/image", response_model=ImagePredictionResponse)
async def predict_image(file: UploadFile = File(...), predictor=Depends(predictor_dependency)):
    """Use case 1 : une photo -> les espèces les plus probables avec un pourcentage de confiance."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit être une image (jpg, png...).")
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image trop lourde (max {config.MAX_UPLOAD_MB} Mo).")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Image illisible.") from exc

    start = time.perf_counter()
    predictions = await run_in_threadpool(predictor.predict, image, config.TOP_K)
    latency_ms = (time.perf_counter() - start) * 1000

    uncertain = predictions[0].confidence < config.CONFIDENCE_THRESHOLD
    STATS["image_requests"] += 1
    STATS["uncertain"] += int(uncertain)
    STATS["total_latency_ms"] += latency_ms
    logger.info("predict top1=%s conf=%.3f latency_ms=%.0f", predictions[0].species_id,
                predictions[0].confidence, latency_ms)

    return ImagePredictionResponse(
        predictions=[
            SpeciesScore(species_id=p.species_id, name_fr=p.name_fr,
                         scientific_name=p.scientific_name, confidence=round(p.confidence, 4))
            for p in predictions
        ],
        uncertain=uncertain,
        suggestion="Confiance faible : décris l'oiseau en mode chat (POST /chat) pour affiner." if uncertain else None,
    )


@app.post("/chat")
def chat(request: ChatRequest):
    """Use case 2 : identification par description (partie ML classique, Bloc 03). À venir."""
    raise HTTPException(status_code=501, detail="Le mode chat n'est pas encore implémenté.")
