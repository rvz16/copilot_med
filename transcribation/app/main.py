import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import COMPUTE_TYPE, DEVICE, MODEL_KAGGLE_DATASET, MODEL_PATH
from app.model import load_model
from app.routes import router
from app.session_audio_context import session_store

# Configure logging for the whole app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _periodic_cleanup():
    while True:
        await asyncio.sleep(60)
        removed = session_store.cleanup_stale()
        if removed > 0:
            logger.info("Cleaned up %d stale session contexts.", removed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Device: %s | Compute: %s | Model: %s | Dataset: %s",
        DEVICE, COMPUTE_TYPE, MODEL_PATH, MODEL_KAGGLE_DATASET,
    )
    load_model()
    logger.info("Model loaded and ready.")

    task = asyncio.create_task(_periodic_cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Whisper STT API",
    version="2.1.0",
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
