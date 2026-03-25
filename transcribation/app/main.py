from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import COMPUTE_TYPE, DEVICE, MODEL_KAGGLE_DATASET, MODEL_PATH
from app.model import load_model
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(
        "Device: %s | Compute: %s | Model: %s | Dataset: %s"
        % (DEVICE, COMPUTE_TYPE, MODEL_PATH, MODEL_KAGGLE_DATASET)
    )
    load_model()
    print("Model loaded and ready.")
    yield


app = FastAPI(
    title="Whisper STT API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "transcribation",
        "device": DEVICE,
        "model_path": str(MODEL_PATH),
    }
