import httpx
from fastapi.testclient import TestClient

from projects.ai_metrics_api import main


client = TestClient(main.app)


class DummyResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def test_ready_skips_backend_probe_by_default(monkeypatch):
    monkeypatch.setattr(main, "MODEL_BACKEND", "mock")
    monkeypatch.setattr(main, "MODEL_SERVER_URL", "http://mock-model-server:8001/generate")
    monkeypatch.setattr(main, "READINESS_CHECK_BACKEND", False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("backend probe should not run")

    monkeypatch.setattr(main.httpx, "post", fail_if_called)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "ai-metrics-api",
        "backend": "mock",
        "model_server_url": "http://mock-model-server:8001/generate",
    }


def test_ready_can_probe_mock_backend(monkeypatch):
    monkeypatch.setattr(main, "MODEL_BACKEND", "mock")
    monkeypatch.setattr(main, "MODEL_SERVER_URL", "http://mock-model-server:8001/generate")
    monkeypatch.setattr(main, "READINESS_CHECK_BACKEND", True)

    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return DummyResponse(200)

    monkeypatch.setattr(main.httpx, "post", fake_post)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["backend_check"] == "ok"
    assert calls[0][0] == "http://mock-model-server:8001/generate"
    assert calls[0][1] == {"model": "readiness", "tokens_in": 1, "tokens_out": 1}


def test_ready_reports_backend_probe_failure(monkeypatch):
    monkeypatch.setattr(main, "MODEL_BACKEND", "mock")
    monkeypatch.setattr(main, "MODEL_SERVER_URL", "http://mock-model-server:8001/generate")
    monkeypatch.setattr(main, "READINESS_CHECK_BACKEND", True)

    def fail_post(*args, **kwargs):
        raise httpx.ConnectError("connection failed")

    monkeypatch.setattr(main.httpx, "post", fail_post)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["detail"] == "model backend readiness check failed: ConnectError"
    assert body["error_code"] == "service_unavailable"
    assert body["request_id"].startswith("req-")
    assert body["trace_id"].startswith("trace-")


def test_ready_can_probe_vllm_backend(monkeypatch):
    monkeypatch.setattr(main, "MODEL_BACKEND", "vllm")
    monkeypatch.setattr(main, "VLLM_BASE_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setattr(main, "READINESS_CHECK_BACKEND", True)

    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return DummyResponse(200)

    monkeypatch.setattr(main.httpx, "get", fake_get)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["backend_check"] == "ok"
    assert calls[0][0] == "http://127.0.0.1:8001/v1/models"
