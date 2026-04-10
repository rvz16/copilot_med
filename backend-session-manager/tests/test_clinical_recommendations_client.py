import httpx

from app.clients.clinical_recommendations import HttpClinicalRecommendationsClient


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_clinical_recommendations_client_gets_search_results(monkeypatch):
    captured: dict = {}

    def fake_get(self, url: str, **kwargs):
        del self
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse(
            {
                "query": "рак легких",
                "items": [
                    {
                        "id": "30_5",
                        "title": "Злокачественное новообразование бронхов и легкого",
                        "pdf_number": 30,
                        "pdf_filename": "КР30.pdf",
                        "pdf_available": True,
                        "score": 3.3448,
                    }
                ],
            }
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    client = HttpClinicalRecommendationsClient("http://recommendations.local", timeout_seconds=5)
    result = client.search("рак легких", limit=1)

    assert captured["url"] == "http://recommendations.local/api/v1/clinical-recommendations/search"
    assert captured["kwargs"]["params"] == {"query": "рак легких", "limit": 1}
    assert result["items"][0]["id"] == "30_5"
