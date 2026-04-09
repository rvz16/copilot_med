from fastapi.testclient import TestClient


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
