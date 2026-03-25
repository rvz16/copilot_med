FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_NAME=qwen3:4b \
    LLM_BASE_URL=http://host.docker.internal:11434 \
    FHIR_BASE_URL=http://158.160.84.63:8092/hapi-fhir-jpaserver/fhir \
    MAX_TOKENS=256 \
    TEMPERATURE=0.0 \
    LLM_TIMEOUT=10.0

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
