"""API BirdsFinder (FastAPI) : identification d'oiseaux par photo (et bientôt par chat)."""
import io
import json
import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from app import chat as chat_mode
from app import config, inference

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("birdsfinder")

app = FastAPI(
    title="BirdsFinder",
    version="0.1.0",
    description="Identifie un oiseau à partir d'une photo (deep learning) ou d'une description (chat).",
)

STATIC_DIR = Path(__file__).parent / "static"

if config.CORS_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])

# Front React compilé (npm run build) : servi par l'API, sinon page de démo historique.
if (config.FRONTEND_DIST / "index.html").exists():
    for sub in ("assets", "ort"):
        if (config.FRONTEND_DIST / sub).is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=config.FRONTEND_DIST / sub), name=f"front-{sub}")

# Compteurs simples pour le monitoring (consultables sur /stats).
STATS = {"image_requests": 0, "uncertain": 0, "total_latency_ms": 0.0, "by_region": {}, "chat_requests": 0}


# ---------- Schémas (contrat de l'API) ----------
class SpeciesScore(BaseModel):
    species_id: str
    name_fr: str
    scientific_name: str | None = None
    confidence: float  # entre 0 et 1


class ImagePredictionResponse(BaseModel):
    region: str  # zone dont le modèle a répondu (antilles, europe)
    predictions: list[SpeciesScore]
    uncertain: bool
    suggestion: str | None = None


class ChatRequest(BaseModel):
    """Toutes les réponses déjà données (le serveur ne garde rien entre deux tours).

    Clé = attribut (voir GET /chat/questions), valeur = un des choix, ou « je ne sais pas ».
    """
    reponses: dict[str, str] = {}


class ChatQuestion(BaseModel):
    attribut: str
    texte: str
    choix: list[str]


class ChatResponse(BaseModel):
    region: str
    predictions: list[SpeciesScore]       # top-3
    question_suivante: ChatQuestion | None
    termine: bool
    nb_reponses: int                       # réponses utiles (hors « je ne sais pas »)
    message: str
    gains: dict[str, float]                # gain d'information de chaque question encore possible (en bits)


# ---------- Dépendances : la zone et son modèle (remplaçables dans les tests) ----------
def region_dependency(region: str | None = Query(None, description="antilles ou europe")) -> str:
    region = region or config.DEFAULT_REGION
    if region not in config.REGION_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Zone inconnue : « {region} ». Zones disponibles : {', '.join(config.REGION_LABELS)}.",
        )
    return region


def predictor_dependency(region: str = Depends(region_dependency)):
    try:
        return inference.get_predictor(region)
    except inference.ModelNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def chat_engine_dependency(region: str = Depends(region_dependency)):
    try:
        return chat_mode.get_engine(region)
    except chat_mode.ChatModelNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _question(engine, attribut: str) -> ChatQuestion:
    return ChatQuestion(attribut=attribut, texte=engine.questions[attribut],
                        choix=engine.valeurs[attribut] + [chat_mode.JE_NE_SAIS_PAS])


# ---------- Routes ----------
@app.get("/", include_in_schema=False)
def home():
    front = config.FRONTEND_DIST / "index.html"
    return FileResponse(front if front.exists() else STATIC_DIR / "index.html")


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    icon = config.FRONTEND_DIST / "favicon.svg"
    if not icon.exists():
        raise HTTPException(status_code=404)
    return FileResponse(icon)


@app.get("/manifest")
def manifest():
    """Même format que manifest.json publié sur le Hugging Face Hub : utilisé par le front en mode "api"."""
    regions_out = {}
    for region, label in config.REGION_LABELS.items():
        model_path, classes_json = config.region_files(region)
        if not model_path.exists() or not classes_json.exists():
            continue
        names = json.loads(classes_json.read_text(encoding="utf-8"))
        # Ordre des classes = ordre alphabétique des dossiers (ImageFolder), comme à l'entraînement
        classes = [
            {"id": slug, "fr": names[slug].get("fr", slug), "sci": names[slug].get("sci") or slug.replace("_", " ")}
            for slug in sorted(names)
        ]
        regions_out[region] = {
            "label": label,
            "version": config.MODEL_VERSION,
            "architecture": "pytorch",
            "img_size": 224,
            "resize": 256,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
            "classes": classes,
        }
    return {"updated_at": None, "regions": regions_out}


@app.get("/health")
def health():
    found = {region: config.region_files(region)[0].exists() for region in config.REGION_LABELS}
    return {
        "status": "ok",
        "model_file_found": found.get(config.DEFAULT_REGION, False),  # modèle de la zone par défaut
        "regions": found,
    }


@app.get("/regions")
def regions():
    """Zones proposées dans l'interface, et si leur modèle est présent sur le serveur."""
    return [
        {
            "id": region,
            "label": label,
            "model_file_found": config.region_files(region)[0].exists(),
            "default": region == config.DEFAULT_REGION,
        }
        for region, label in config.REGION_LABELS.items()
    ]


@app.get("/stats")
def stats():
    n = STATS["image_requests"]
    return {
        "image_requests": n,
        "uncertain_predictions": STATS["uncertain"],
        "avg_latency_ms": round(STATS["total_latency_ms"] / n, 1) if n else None,
        "by_region": STATS["by_region"],
        "chat_requests": STATS["chat_requests"],
    }


@app.post("/predict/image", response_model=ImagePredictionResponse)
async def predict_image(
    file: UploadFile = File(...),
    region: str = Depends(region_dependency),
    predictor=Depends(predictor_dependency),
):
    """Use case 1 : une photo -> les espèces les plus probables avec un pourcentage de confiance.

    `?region=antilles` ou `?region=europe` choisit le modèle (par défaut : DEFAULT_REGION).
    """
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
    STATS["by_region"][region] = STATS["by_region"].get(region, 0) + 1
    logger.info("predict region=%s top1=%s conf=%.3f latency_ms=%.0f", region, predictions[0].species_id,
                predictions[0].confidence, latency_ms)

    return ImagePredictionResponse(
        region=region,
        predictions=[
            SpeciesScore(species_id=p.species_id, name_fr=p.name_fr,
                         scientific_name=p.scientific_name, confidence=round(p.confidence, 4))
            for p in predictions
        ],
        uncertain=uncertain,
        suggestion="Confiance faible : décris l'oiseau en mode chat (POST /chat) pour affiner." if uncertain else None,
    )


@app.get("/chat/questions", response_model=list[ChatQuestion])
def chat_questions(engine=Depends(chat_engine_dependency)):
    """Les 12 questions du mode chat et leurs réponses possibles."""
    return [_question(engine, a) for a in engine.attributs]


@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    region: str = Depends(region_dependency),
    engine=Depends(chat_engine_dependency),
):
    """Use case 2 : identification par description (ML classique, Bloc 03).

    1er appel avec `{"reponses": {}}` : l'API renvoie la question la plus utile à poser.
    Ensuite, renvoyer toutes les réponses à chaque tour jusqu'à `termine: true`.
    """
    try:
        result = engine.tour(request.reponses)
    except chat_mode.InvalidAnswer as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    STATS["chat_requests"] += 1
    top, conf = result.predictions[0]
    logger.info("chat region=%s reponses=%d top1=%s conf=%.3f question=%s", region, result.nb_reponses,
                top["id"], conf, result.question)
    return ChatResponse(
        region=region,
        predictions=[
            SpeciesScore(species_id=e["id"], name_fr=e["fr"], scientific_name=e.get("sci"), confidence=round(p, 4))
            for e, p in result.predictions[: config.TOP_K]
        ],
        question_suivante=_question(engine, result.question) if result.question else None,
        termine=result.termine,
        nb_reponses=result.nb_reponses,
        message=chat_mode.phrase(result),
        gains=result.gains,
    )
