# Clinical Recommendations Service

## Purpose

This service makes the local clinical recommendations dataset searchable and serves the corresponding PDFs when they are available on disk.

The data itself lives outside the service folder:

- CSV: `clinical_recommendations/clinical_recommendations.csv`
- PDFs: `clinical_recommendations/pdf_files/`

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app bootstrap |
| `app/api/routes.py` | list/search/detail/pdf endpoints |
| `app/services/recommendations.py` | CSV loading, normalization, search scoring, PDF resolution |
| `app/schemas.py` | public response models |
| `app/core/config.py` | resolves CSV and PDF paths |

## Startup Behavior

At startup the service:

1. reads the semicolon-delimited CSV
2. builds `ClinicalRecommendationEntry` objects
3. derives `pdf_number` from each recommendation ID
4. maps that number to a filename like `КР286.pdf`
5. checks whether the PDF exists locally
6. stores all entries in memory

The service does not use a database.

## Search Behavior

Search is implemented in `app/services/recommendations.py`.

The search pipeline:

- normalizes Russian text
- tokenizes and stems words
- drops stopwords
- expands some domain synonyms
- scores entries using token coverage, synonym overlap, phrase inclusion, and sequence similarity

This is a lightweight fuzzy search tuned for Russian disease titles.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | liveness |
| `GET` | `/api/v1/clinical-recommendations` | paginated list |
| `GET` | `/api/v1/clinical-recommendations/search` | keyword search |
| `GET` | `/api/v1/clinical-recommendations/{id}` | detail record |
| `GET` | `/api/v1/clinical-recommendations/{id}/pdf` | PDF file download |

## PDF Dependency

The service assumes the official PDF files have already been downloaded into:

```text
clinical_recommendations/pdf_files/
```

Download source:

- [Google Drive folder with PDFs](https://drive.google.com/drive/folders/1m0AiEByrTHS7VP8iqhYoppIbBisRsARw?usp=sharing)

If the directory exists but a specific PDF is missing:

- the entry still appears in list and search results
- `pdf_available` is `false`
- the PDF endpoint returns `404 PDF_NOT_FOUND`

## Why This Service Matters in the Stack

`session-manager` uses it in two places:

- during live analysis, to attach guideline PDFs to strong diagnosis suggestions
- during post-session analytics, to attach additional recommendation PDFs for final impressions

## Tests

Tests live in:

- `clinical-recommendations-service/tests/test_api.py`

They verify:

- list pagination
- PDF availability filtering
- fuzzy search
- missing recommendation behavior
- missing PDF behavior
