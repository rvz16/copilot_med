FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=container \
    HOST=0.0.0.0 \
    PORT=8002 \
    CLINICAL_RECOMMENDATIONS_CSV_PATH=/app/clinical_recommendations/clinical_recommendations.csv \
    CLINICAL_RECOMMENDATIONS_PDF_DIR=/app/clinical_recommendations/generated/pdf_files \
    CLINICAL_RECOMMENDATIONS_PDF_ARCHIVE_PATH=/app/clinical_recommendations/generated/pdf_archive.zip \
    CLINICAL_RECOMMENDATIONS_EMBEDDINGS_PATH=/app/clinical_recommendations/recommendation_embeddings.parquet \
    CLINICAL_RECOMMENDATIONS_EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-small \
    CLINICAL_RECOMMENDATIONS_EMBEDDING_QUERY_PREFIX="query: " \
    CLINICAL_RECOMMENDATIONS_EMBEDDING_PASSAGE_PREFIX="passage: "

WORKDIR /app

COPY clinical-recommendations-service/requirements.txt ./

RUN pip install -r requirements.txt

COPY clinical-recommendations-service/app ./app
COPY clinical_recommendations/clinical_recommendations.csv ./clinical_recommendations/clinical_recommendations.csv
COPY clinical_recommendations/recommendation_embeddings.parquet ./clinical_recommendations/recommendation_embeddings.parquet
RUN mkdir -p ./clinical_recommendations/generated/pdf_files

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8002

CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8002}"]
