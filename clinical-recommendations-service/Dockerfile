FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=container \
    HOST=0.0.0.0 \
    PORT=8002 \
    CLINICAL_RECOMMENDATIONS_CSV_PATH=/app/clinical_recommendations/clinical_recommendations.csv \
    CLINICAL_RECOMMENDATIONS_PDF_DIR=/app/clinical_recommendations/pdf_files

WORKDIR /app

COPY clinical-recommendations-service/requirements.txt ./

RUN pip install -r requirements.txt

COPY clinical-recommendations-service/app ./app
COPY clinical_recommendations/clinical_recommendations.csv ./clinical_recommendations/clinical_recommendations.csv
RUN mkdir -p ./clinical_recommendations/pdf_files

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8002

CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8002}"]
