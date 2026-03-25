import httpx

from app.fhir import FhirClient


def test_create_resource_success(monkeypatch) -> None:
    def fake_post(self, url, json):  # type: ignore[no-untyped-def]
        request = httpx.Request("POST", url, json=json)
        return httpx.Response(
            201,
            request=request,
            json={"resourceType": "Condition", "id": "cond-1"},
            headers={"Location": f"{url}/cond-1/_history/1"},
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = FhirClient(base_url="http://fhir", timeout_seconds=1.0, max_retries=1)
    result = client.create_resource("Condition", {"resourceType": "Condition"})

    assert result["ok"] is True
    assert result["id"] == "cond-1"
    assert result["status_code"] == 201


def test_create_resource_retries_on_timeout(monkeypatch) -> None:
    call_count = {"count": 0}

    def fake_post(self, url, json):  # type: ignore[no-untyped-def]
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise httpx.TimeoutException("timeout")

        request = httpx.Request("POST", url, json=json)
        return httpx.Response(201, request=request, json={"id": "obs-1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = FhirClient(base_url="http://fhir", timeout_seconds=1.0, max_retries=1)
    result = client.create_resource("Observation", {"resourceType": "Observation"})

    assert call_count["count"] == 2
    assert result["ok"] is True


def test_create_resource_returns_error_on_http_failure(monkeypatch) -> None:
    def fake_post(self, url, json):  # type: ignore[no-untyped-def]
        request = httpx.Request("POST", url, json=json)
        return httpx.Response(400, request=request, text="invalid payload")

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = FhirClient(base_url="http://fhir", timeout_seconds=1.0, max_retries=0)
    result = client.create_resource("MedicationStatement", {"resourceType": "MedicationStatement"})

    assert result["ok"] is False
    assert result["status_code"] == 400
    assert "invalid payload" in result["error"]
