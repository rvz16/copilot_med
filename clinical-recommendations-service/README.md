# Clinical Recommendations Service

Standalone FastAPI microservice for official clinical recommendations lookup. It loads the CSV from [`../clinical_recommendations/clinical_recommendations.csv`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical_recommendations/clinical_recommendations.csv), exposes searchable disease metadata, and serves the corresponding recommendation PDF when it exists.

## Features

- loads all 707 CSV entries into an in-memory store on startup
- lists recommendation entries with pagination and optional `has_pdf` filtering
- searches diseases by Russian keywords and returns official recommendation ids
- maps recommendation ids like `286_3` to PDF names like `КР286.pdf`
- downloads the original PDF if it is present in [`../clinical_recommendations/pdf_files/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical_recommendations/pdf_files)

## Local Setup

From [`clinical-recommendations-service/`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical-recommendations-service):

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

The default configuration resolves the CSV and PDF directory from the repository root automatically.

## Docker

Build from the repository root because the image needs both the service code and the `clinical_recommendations/` data directory:

```bash
docker build -f clinical-recommendations-service/Dockerfile -t clinical-recommendations-service .
```

Run:

```bash
docker run --rm -p 8002:8002 clinical-recommendations-service
```

## Endpoints

- `GET /health`
- `GET /api/v1/clinical-recommendations`
- `GET /api/v1/clinical-recommendations/search`
- `GET /api/v1/clinical-recommendations/{recommendation_id}`
- `GET /api/v1/clinical-recommendations/{recommendation_id}/pdf`

## Curl Examples

List entries:

```bash
curl "http://localhost:8002/api/v1/clinical-recommendations?limit=5&offset=0"
```

Search:

```bash
curl "http://localhost:8002/api/v1/clinical-recommendations/search?query=%D1%80%D0%B0%D0%BA%20%D0%BB%D0%B5%D0%B3%D0%BA%D0%B8%D1%85"
```

Get one entry:

```bash
curl "http://localhost:8002/api/v1/clinical-recommendations/30_5"
```

Download PDF:

```bash
curl -OJ "http://localhost:8002/api/v1/clinical-recommendations/30_5/pdf"
```

## Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `APP_NAME` | `Clinical Recommendations Service` | FastAPI title |
| `HOST` | `0.0.0.0` | Uvicorn host |
| `PORT` | `8002` | Service port |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed browser origins |
| `CLINICAL_RECOMMENDATIONS_CSV_PATH` | repo `clinical_recommendations/clinical_recommendations.csv` | CSV source |
| `CLINICAL_RECOMMENDATIONS_PDF_DIR` | repo `clinical_recommendations/pdf_files` | PDF directory |

## Tests

```bash
.venv/bin/pytest
```
