from fastapi.testclient import TestClient

from app.services.embeddings import EmbeddingSearchMatch
from app.services.recommendations import ClinicalRecommendationsService


def test_health_check_returns_200(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "clinical-recommendations"}


def test_list_recommendations_returns_paginated_entries(client: TestClient):
    response = client.get(
        "/api/v1/clinical-recommendations",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert body["total"] == 4
    assert [item["id"] for item in body["items"]] == ["603_3", "379_4"]


def test_list_recommendations_can_filter_by_pdf_presence(client: TestClient):
    response = client.get(
        "/api/v1/clinical-recommendations",
        params={"has_pdf": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {"30_5", "379_4"}


def test_get_recommendation_returns_entry_details(client: TestClient):
    response = client.get("/api/v1/clinical-recommendations/286_3")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "286_3"
    assert body["title"] == "Сахарный диабет 1 типа у взрослых"
    assert body["icd10_codes"] == ["E10.2", "E10.3"]
    assert body["pdf_filename"] == "КР286.pdf"
    assert body["pdf_available"] is False


def test_search_returns_best_matching_disease_id(client: TestClient):
    response = client.get(
        "/api/v1/clinical-recommendations/search",
        params={"query": "рак легких", "limit": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "рак легких"
    assert body["items"][0]["id"] == "30_5"
    assert body["items"][0]["pdf_available"] is True
    assert body["items"][0]["score"] > body["items"][1]["score"]


def test_post_search_accepts_transcript_body(client: TestClient):
    response = client.post(
        "/api/v1/clinical-recommendations/search",
        json={"query": "Пациент кашляет, есть подозрение на рак легких.", "limit": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == "30_5"


def test_search_uses_embedding_index_when_available(sample_data):
    csv_path, pdf_dir = sample_data

    class FakeEmbeddingIndex:
        def search(self, query: str, *, limit: int):
            assert query == "текст консультации"
            assert limit == 100
            return [EmbeddingSearchMatch(recommendation_id="379_4", score=0.9123)]

    service = ClinicalRecommendationsService(
        csv_path=csv_path,
        pdf_dir=pdf_dir,
        embedding_index=FakeEmbeddingIndex(),
        embeddings_enabled=True,
    )

    results = service.search(query="текст консультации", limit=2)

    assert [result.entry.id for result in results] == ["379_4"]
    assert results[0].score == 0.9123


def test_search_backfills_pdf_result_when_embeddings_fail(sample_data):
    csv_path, pdf_dir = sample_data

    class FailingEmbeddingIndex:
        def search(self, query: str, *, limit: int):
            del query, limit
            raise RuntimeError("embedding backend unavailable")

    service = ClinicalRecommendationsService(
        csv_path=csv_path,
        pdf_dir=pdf_dir,
        embedding_index=FailingEmbeddingIndex(),
        embeddings_enabled=True,
    )

    results = service.search(query="полидипсия, жажда и хроническая усталость", limit=2)

    assert results
    assert any(result.entry.pdf_available for result in results)


def test_blank_search_query_returns_400(client: TestClient):
    response = client.get(
        "/api/v1/clinical-recommendations/search",
        params={"query": "   "},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_QUERY"


def test_download_pdf_returns_file(client: TestClient):
    response = client.get("/api/v1/clinical-recommendations/30_5/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "filename*=" in response.headers["content-disposition"]
    assert response.content == b"%PDF-1.4\nlung-cancer\n"


def test_download_pdf_returns_404_when_missing(client: TestClient):
    response = client.get("/api/v1/clinical-recommendations/603_3/pdf")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PDF_NOT_FOUND"


def test_missing_recommendation_returns_404(client: TestClient):
    response = client.get("/api/v1/clinical-recommendations/missing_id")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RECOMMENDATION_NOT_FOUND"
