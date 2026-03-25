from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import DEVICE, COMPUTE_TYPE, MODEL_PATH
from app.model import load_model
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Device: {DEVICE} | Compute: {COMPUTE_TYPE} | Model: {MODEL_PATH}")
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
    return {"status": "ok", "device": DEVICE}
