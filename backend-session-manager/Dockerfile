FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=container \
    HOST=0.0.0.0 \
    PORT=8080 \
    DATABASE_URL=sqlite:///./data/session_manager.db \
    STORAGE_DIR=./data/storage

WORKDIR /app

COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY app ./app

RUN adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data/storage \
    && chown -R appuser:appuser /app

USER appuser

VOLUME ["/app/data"]

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]
