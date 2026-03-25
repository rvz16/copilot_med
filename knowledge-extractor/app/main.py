from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(router)
