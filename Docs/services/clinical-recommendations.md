# Clinical Recommendations Service

## Purpose

This service makes the local clinical recommendations dataset searchable and serves the corresponding PDFs when they are available on disk. It now uses embeddings built from the PDF text for transcript-based retrieval, with the previous title fuzzy search retained as a fallback.

The data itself lives outside the service folder:

- CSV: `clinical_recommendations/clinical_recommendations.csv`
- PDFs: `clinical_recommendations/pdf_files/` locally, or `/app/clinical_recommendations/generated/pdf_files` in Docker
- embedding index: `clinical_recommendations/recommendation_embeddings.parquet` locally, or `/app/clinical_recommendations/recommendation_embeddings.parquet` in Docker

## Main Files

| File | Role |
| --- | --- |
| `app/main.py` | FastAPI app bootstrap |
| `app/api/routes.py` | list/search/detail/pdf endpoints |
| `app/services/recommendations.py` | CSV loading, normalization, search scoring, PDF resolution |
| `app/services/pdf_assets.py` | Google Drive archive download and safe PDF extraction |
| `app/services/embeddings.py` | PDF text extraction, BERT embeddings, parquet persistence, cosine search |
| `app/scripts/build_recommendation_embeddings.py` | one-shot embedding/index rebuild script |
| `app/schemas.py` | public response models |
| `app/core/config.py` | resolves CSV and PDF paths |

## Startup Behavior

At startup the service:

1. ensures the PDF directory exists
2. if no PDFs are present, downloads the configured Google Drive archive and extracts PDFs from it
3. reads the semicolon-delimited CSV
4. builds `ClinicalRecommendationEntry` objects
5. derives `pdf_number` from each recommendation ID
6. maps that number to a filename like `КР286.pdf`
7. checks whether the PDF exists locally
8. loads the tracked parquet embedding index, or rebuilds it only if metadata no longer matches the available PDFs
9. stores all entries in memory

The service does not use a database.

## Search Behavior

Search is implemented in `app/services/recommendations.py` and `app/services/embeddings.py`.

The primary semantic pipeline:

- extracts text from each available PDF using PyMuPDF
- truncates extracted text to `CLINICAL_RECOMMENDATIONS_EMBEDDING_TOKEN_LIMIT`, 512 by default
- embeds documents with the configured Hugging Face encoder, `intfloat/multilingual-e5-small` by default
- uses the E5 `query: ` and `passage: ` prefixes unless overridden by environment variables
- writes document embeddings and source metadata to parquet
- embeds the live or final transcript and ranks PDFs by cosine similarity
- blends cosine scores with the Russian title matcher so exact disease/title matches stay stable for short queries

The fallback fuzzy pipeline:

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
| `GET` | `/api/v1/clinical-recommendations/search` | keyword/transcript search |
| `POST` | `/api/v1/clinical-recommendations/search` | transcript search body for longer inputs |
| `GET` | `/api/v1/clinical-recommendations/{id}` | detail record |
| `GET` | `/api/v1/clinical-recommendations/{id}/pdf` | PDF file download |

## PDF Dependency

The service can still use official PDF files already downloaded into:

```text
clinical_recommendations/pdf_files/
```

Download source:

- [Google Drive archive with PDFs](https://drive.google.com/file/d/1-tZTEmoXcfsAGbvxUhCQpkDxprB3K3EP/view?usp=sharing)

In the root Docker Compose stack, PDFs and the archive cache live in the named volume `clinical-recommendations-data`. The parquet index is tracked in git and copied into the service image so fresh clones do not need to rebuild embeddings.

If the directory exists but a specific PDF is missing:

- the entry still appears in list and search results
- `pdf_available` is `false`
- the PDF endpoint returns `404 PDF_NOT_FOUND`

## Why This Service Matters in the Stack

`session-manager` uses it in two places:

- during live analysis, to attach guideline PDFs based on the current stable transcript
- during post-session analytics, to attach additional recommendation PDFs based on the final transcript and analytics impressions

## Tests

Tests live in:

- `clinical-recommendations-service/tests/test_api.py`

They verify:

- list pagination
- PDF availability filtering
- fuzzy search
- missing recommendation behavior
- missing PDF behavior
