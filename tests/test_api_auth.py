from fastapi.testclient import TestClient

from projects.ai_metrics_api import main


client = TestClient(main.app)


def fake_call_model_server(payload):
    return {
        "model": payload["model"],
        "status": 200,
        "latency_ms": 12,
        "tokens_in": payload["tokens_in"],
        "tokens_out": payload["tokens_out"],
    }


def enable_auth(monkeypatch, api_key="test-key"):
    monkeypatch.setattr(main, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(main, "API_KEY", api_key)


def test_infer_allows_requests_when_auth_is_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REQUIRE_API_KEY", False)
    monkeypatch.setattr(main, "LOG_PATH", str(tmp_path / "inference.log"))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    response = client.post("/v1/infer", json={"model": "qwen", "tokens_in": 1, "tokens_out": 2})

    assert response.status_code == 200
    assert response.json()["status"] == 200


def test_infer_rejects_missing_api_key(monkeypatch):
    enable_auth(monkeypatch)

    response = client.post("/v1/infer", json={"model": "qwen", "tokens_in": 1, "tokens_out": 2})

    assert response.status_code == 401
    assert response.json()["detail"] == "missing API key"


def test_infer_rejects_invalid_bearer_token(monkeypatch):
    enable_auth(monkeypatch)

    response = client.post(
        "/v1/infer",
        headers={"Authorization": "Bearer wrong-key"},
        json={"model": "qwen", "tokens_in": 1, "tokens_out": 2},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid API key"


def test_infer_accepts_valid_bearer_token(monkeypatch, tmp_path):
    enable_auth(monkeypatch)
    monkeypatch.setattr(main, "LOG_PATH", str(tmp_path / "inference.log"))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    response = client.post(
        "/v1/infer",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "qwen", "tokens_in": 1, "tokens_out": 2},
    )

    assert response.status_code == 200
    assert response.json()["status"] == 200


def test_mock_infer_accepts_valid_x_api_key(monkeypatch, tmp_path):
    enable_auth(monkeypatch)
    monkeypatch.setattr(main, "LOG_PATH", str(tmp_path / "inference.log"))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    response = client.post(
        "/v1/mock-infer",
        headers={"X-API-Key": "test-key"},
        json={"model": "qwen", "tokens_in": 1, "tokens_out": 2},
    )

    assert response.status_code == 200
    assert response.json()["status"] == 200


def test_health_and_readiness_do_not_require_api_key(monkeypatch):
    enable_auth(monkeypatch)

    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200


def test_enabled_auth_requires_configured_api_key(monkeypatch):
    enable_auth(monkeypatch, api_key="")

    response = client.post(
        "/v1/infer",
        headers={"Authorization": "Bearer test-key"},
        json={"model": "qwen", "tokens_in": 1, "tokens_out": 2},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "API key authentication is enabled but API_KEY is not configured"
