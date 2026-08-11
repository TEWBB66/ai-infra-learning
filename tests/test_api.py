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

def test_metrics_api_readiness_mock_backend(monkeypatch):
    from projects.ai_metrics_api import main

    monkeypatch.setattr(main, "MODEL_BACKEND", "mock")
    monkeypatch.setattr(main, "MODEL_SERVER_URL", "http://mock-model-server:8001/generate")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "ai-metrics-api",
        "backend": "mock",
        "model_server_url": "http://mock-model-server:8001/generate",
    }


def test_metrics_api_readiness_remote_http_backend(monkeypatch):
    from projects.ai_metrics_api import main

    monkeypatch.setattr(main, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(main, "MODEL_SERVER_URL", "http://127.0.0.1:8002/generate")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "ai-metrics-api",
        "backend": "remote_http",
        "model_server_url": "http://127.0.0.1:8002/generate",
    }


def test_metrics_api_readiness_rejects_unsupported_backend(monkeypatch):
    from projects.ai_metrics_api import main

    monkeypatch.setattr(main, "MODEL_BACKEND", "unsupported")

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "unsupported MODEL_BACKEND: unsupported"

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


def test_mock_infer_success(monkeypatch, tmp_path):
    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(
        "projects.ai_metrics_api.main.LOG_PATH",
        str(temp_log_path),
    )

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
    assert "ai_inference_model_requests" in body

def test_prometheus_metrics_include_model_level_metrics():
    response = client.get("/metrics/prometheus")

    assert response.status_code == 200

    body = response.text
    assert 'ai_inference_model_requests{model="qwen2.5-7b"}' in body
    assert 'ai_inference_model_errors{model="qwen2.5-7b"}' in body
    assert 'ai_inference_model_error_rate{model="qwen2.5-7b"}' in body
    assert 'ai_inference_model_p95_latency_ms{model="qwen2.5-7b"}' in body

def test_incident_report_endpoint():
    response = client.get("/metrics/incidents")

    assert response.status_code == 200
    data = response.json()

    assert "service_status" in data
    assert data["service_status"] in ["healthy", "warning", "critical"]

    assert "summary" in data
    assert "total_requests" in data
    assert "error_rate" in data
    assert "p95_latency_ms" in data
    assert "slow_request_count" in data
    assert "alert_count" in data

    assert "possible_causes" in data
    assert isinstance(data["possible_causes"], list)

    assert "suggested_actions" in data
    assert isinstance(data["suggested_actions"], list)

def test_mock_infer_logs_backend_failure(monkeypatch, tmp_path):
    from fastapi import HTTPException
    from projects.ai_metrics_api import main

    temp_log_path = tmp_path / "inference.log"

    def fake_call_model_server(payload):
        raise HTTPException(status_code=502, detail="model server is unavailable")

    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    response = client.post(
        "/v1/mock-infer",
        json={
            "model": "qwen2.5-0.5b",
            "tokens_in": 100,
            "tokens_out": 20,
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "model server is unavailable"

    log_text = temp_log_path.read_text()
    assert "model=qwen2.5-0.5b" in log_text
    assert "endpoint=/v1/mock-infer" in log_text
    assert "status=502" in log_text
    assert "tokens_in=100" in log_text
    assert "tokens_out=0" in log_text
