import pytest
from fastapi.testclient import TestClient

from app.api.routes_query import get_service
from app.main import app

from .conftest import FailingLLM

URL = "/v1/query"


@pytest.fixture
def client_with(make_service):
    """A test client whose /v1/query uses a fake service. Startup (models, Qdrant) is skipped."""
    def _client(**kwargs):
        service, llm, store = make_service(**kwargs)
        app.dependency_overrides[get_service] = lambda: service
        return TestClient(app), llm, store
    yield _client
    app.dependency_overrides.clear()


def test_health_is_ok(client_with):
    client, _, _ = client_with()
    assert client.get("/health").json() == {"status": "ok"}


def test_query_returns_full_response_shape(client_with):
    client, _, _ = client_with()
    body = client.post(URL, json={"query": "Laptop allowance in EMEA?"}).json()
    assert body["status"] == "answered"
    assert {"answer", "citations", "refusal_reason", "trace_id", "latency_ms"} <= body.keys()
    assert body["citations"][0]["document_id"] == "IT-SPEC-2025-A"


def test_empty_query_is_rejected(client_with):
    client, _, _ = client_with()
    assert client.post(URL, json={"query": ""}).status_code == 422


def test_invalid_tenant_header_is_rejected(client_with):
    client, _, _ = client_with()
    resp = client.post(URL, json={"query": "Laptop?"}, headers={"X-Tenant-ID": "ACME!!"})
    assert resp.status_code == 422


def test_tenant_header_reaches_the_service(client_with):
    client, _, store = client_with()
    client.post(URL, json={"query": "Laptop?"}, headers={"X-Tenant-ID": "globex"})
    assert store.calls[0]["tenant_id"] == "globex"


def test_llm_failure_returns_503(client_with):
    client, _, _ = client_with(llm=FailingLLM())
    resp = client.post(URL, json={"query": "Laptop allowance in EMEA?"})
    assert resp.status_code == 503
    assert "temporarily unavailable" in resp.json()["detail"]


def test_ready_is_503_when_store_is_missing(client_with):
    client, _, _ = client_with()
    assert client.get("/ready").status_code == 503