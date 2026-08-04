from fastapi.testclient import TestClient

from projects.ai_metrics_api.main import app


client = TestClient(app)

class FakeModelServerResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "model": "bge-reranker",
            "status": 200,
            "latency_ms": 66,
            "tokens_in": 10,
            "tokens_out": 0,
        }


def fake_model_server_post(*args, **kwargs):
    return FakeModelServerResponse()

def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_logs():
    response = client.get("/metrics/logs")

    assert response.status_code == 200

    data = response.json()
    assert "total_requests" in data
    assert "error_rate" in data
    assert "p95_latency_ms" in data
    assert "metrics_by_model" in data


def test_metrics_models():
    response = client.get("/metrics/models")

    assert response.status_code == 200

    data = response.json()
    assert "metrics_by_model" in data

def test_metrics_alerts():
    response = client.get("/metrics/alerts")

    assert response.status_code == 200

    data = response.json()
    assert "service_status" in data
    assert "alert_count" in data
    assert "alerts" in data
    assert data["service_status"] in ["healthy", "warning", "critical"]


def test_metrics_model_filter_existing_model():
    response = client.get("/metrics/models?model_name=qwen2.5-7b")

    assert response.status_code == 200

    data = response.json()
    assert data["model_name"] == "qwen2.5-7b"
    assert "metrics" in data


def test_metrics_model_filter_unknown_model():
    response = client.get("/metrics/models?model_name=unknown-model")

    assert response.status_code == 404
    assert response.json()["detail"] == "model not found"

def fake_call_model_server(payload):
    return {
        "model": payload["model"],
        "status": payload.get("force_status") or 200,
        "latency_ms": 66,
        "tokens_in": payload["tokens_in"],
        "tokens_out": payload["tokens_out"],
    }


def test_mock_infer_success(monkeypatch):
    monkeypatch.setattr(
        "projects.ai_metrics_api.main.call_model_server",
        fake_call_model_server,
    )

    response = client.post(
        "/v1/mock-infer",
        json={
            "model": "bge-reranker",
            "tokens_in": 10,
            "tokens_out": 0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "bge-reranker"
    assert data["status"] == 200
    assert data["latency_ms"] == 66
    assert data["tokens_in"] == 10
    assert data["tokens_out"] == 0
    assert "request_id" in data


def test_mock_infer_rejects_negative_tokens():
    response = client.post(
        "/v1/mock-infer",
        json={
            "model": "qwen2.5-7b",
            "tokens_in": -1,
            "tokens_out": 0,
        },
    )

    assert response.status_code == 422


def test_mock_infer_rejects_invalid_force_status():
    response = client.post(
        "/v1/mock-infer",
        json={
            "model": "qwen2.5-7b",
            "tokens_in": 10,
            "tokens_out": 0,
            "force_status": 999,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "force_status must be one of 200, 400, 429, 500"

def test_prometheus_metrics():
    response = client.get("/metrics/prometheus")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    assert "ai_inference_total_requests" in body
    assert "ai_inference_error_rate" in body
    assert "ai_inference_p95_latency_ms" in body
    assert "ai_inference_model_request_count" in body