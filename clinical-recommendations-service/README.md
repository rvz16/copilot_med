# Clinical Recommendations Service

Standalone FastAPI microservice for official clinical recommendations lookup. It loads the CSV from [`../clinical_recommendations/clinical_recommendations.csv`](/Users/bulatsaripov/Desktop/Courses_Inno/AI_In_Healthcare/Project/copilot_med/clinical_recommendations/clinical_recommendations.csv), ensures recommendation PDFs exist, builds BERT embeddings from extracted PDF text, and serves the corresponding recommendation PDF when it exists.

## Features

- loads all 707 CSV entries into an in-memory store on startup
- downloads and unpacks the Google Drive PDF archive when the PDF directory is empty
- extracts Russian PDF text with PyMuPDF, truncates it to the configured model token limit, and stores embeddings in parquet
- lists recommendation entries with pagination and optional `has_pdf` filtering
- searches by consultation transcript or disease text using cosine similarity over PDF embeddings
- blends cosine similarity with the Russian title matcher to keep short disease queries precise
- falls back to the previous Russian fuzzy title search if embeddings are disabled or unavailable
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

Build or refresh the embedding parquet explicitly:

```bash
python -m app.scripts.build_recommendation_embeddings --force
```

## Docker

Build from the repository root because the image needs both the service code and the `clinical_recommendations/` data directory:

```bash
docker build -f clinical-recommendations-service/Dockerfile -t clinical-recommendations-service .
```

Run:

```bash
docker run --rm -p 8002:8002 -v clinical-recommendations-data:/app/clinical_recommendations/generated clinical-recommendations-service
```

The first container startup can take a while because it downloads and extracts the PDF archive. The parquet embedding index is tracked in git and copied into the image, so it is only rebuilt when the tracked index no longer matches the available PDFs or embedding settings.

## Endpoints

- `GET /health`
- `GET /api/v1/clinical-recommendations`
- `GET /api/v1/clinical-recommendations/search`
- `POST /api/v1/clinical-recommendations/search`
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

Search with transcript body:

```bash
curl -X POST "http://localhost:8002/api/v1/clinical-recommendations/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"Пациент жалуется на кашель, одышку и боль в груди.","limit":3}'
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
| `CLINICAL_RECOMMENDATIONS_PDF_DOWNLOAD_ENABLED` | `true` | Download and extract archive if no PDFs exist |
| `CLINICAL_RECOMMENDATIONS_PDF_ARCHIVE_URL` | Google Drive file URL | Source archive for PDFs |
| `CLINICAL_RECOMMENDATIONS_PDF_ARCHIVE_PATH` | repo `clinical_recommendations/pdf_archive.zip` | Local archive cache |
| `CLINICAL_RECOMMENDATIONS_EMBEDDINGS_ENABLED` | `true` | Enable PDF embedding search |
| `CLINICAL_RECOMMENDATIONS_EMBEDDINGS_PATH` | repo `clinical_recommendations/recommendation_embeddings.parquet` | Tracked embedding index |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_MODEL_NAME` | `intfloat/multilingual-e5-small` | Hugging Face encoder model |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_QUERY_PREFIX` | `query: ` | Prefix for E5 query embeddings |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_PASSAGE_PREFIX` | `passage: ` | Prefix for E5 document embeddings |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_TOKEN_LIMIT` | `512` | Max extracted/query tokens used by the encoder |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_BATCH_SIZE` | `8` | Embedding build batch size |
| `CLINICAL_RECOMMENDATIONS_EMBEDDING_MIN_SCORE` | `0.15` | Minimum cosine similarity returned from embedding search |

## Tests

```bash
.venv/bin/pytest
```
