from fastapi.testclient import TestClient

from projects.ai_metrics_api import main
from projects.ai_metrics_api.rate_limiter import FixedWindowRateLimiter


client = TestClient(main.app)


def fake_call_model_server(payload):
    return {
        "model": payload["model"],
        "status": 200,
        "latency_ms": 25,
        "tokens_in": payload["tokens_in"],
        "tokens_out": payload["tokens_out"],
    }


def reset_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(tmp_path / "contract.log"))
    monkeypatch.setattr(main, "REQUIRE_API_KEY", False)
    monkeypatch.setattr(main, "RATE_LIMITER", FixedWindowRateLimiter(False, 60, 60))
    monkeypatch.setattr(main, "INFERENCE_GATE", main.InferenceGate(8))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)


def test_health_response_contract():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-metrics-api",
    }


def test_ready_response_contract_for_mock_backend(monkeypatch):
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


def test_ready_response_contract_for_vllm_backend(monkeypatch):
    monkeypatch.setattr(main, "MODEL_BACKEND", "vllm")
    monkeypatch.setattr(main, "VLLM_BASE_URL", "http://127.0.0.1:8001/v1")
    monkeypatch.setattr(main, "VLLM_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "ai-metrics-api",
        "backend": "vllm",
        "vllm_base_url": "http://127.0.0.1:8001/v1",
        "vllm_model": "Qwen/Qwen2.5-0.5B-Instruct",
    }


def test_infer_success_response_contract(monkeypatch, tmp_path):
    reset_runtime(monkeypatch, tmp_path)

    response = client.post(
        "/v1/infer",
        headers={
            "X-Request-ID": "req-contract-1",
            "X-Trace-ID": "trace-contract-1",
            "X-Client-ID": "client-contract-1",
        },
        json={"model": "qwen", "tokens_in": 8, "tokens_out": 16},
    )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "req-contract-1",
        "trace_id": "trace-contract-1",
        "model": "qwen",
        "status": 200,
        "latency_ms": 25,
        "tokens_in": 8,
        "tokens_out": 16,
    }


def test_error_response_contract_keeps_stable_fields(monkeypatch):
    monkeypatch.setattr(main, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(main, "API_KEY", "test-key")

    response = client.post(
        "/v1/infer",
        headers={
            "X-Request-ID": "req-contract-error",
            "X-Trace-ID": "trace-contract-error",
        },
        json={"model": "qwen", "tokens_in": 8, "tokens_out": 16},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "missing API key",
        "error_code": "auth_missing",
        "message": "missing API key",
        "request_id": "req-contract-error",
        "trace_id": "trace-contract-error",
    }


def test_prometheus_response_contract(monkeypatch, tmp_path):
    reset_runtime(monkeypatch, tmp_path)

    client.post(
        "/v1/infer",
        headers={"X-Request-ID": "req-prom-contract"},
        json={"model": "qwen", "tokens_in": 8, "tokens_out": 16},
    )

    response = client.get("/metrics/prometheus")

    assert response.status_code == 200
    body = response.text
    required_lines = [
        "# HELP ai_inference_total_requests Total number of inference requests",
        "# TYPE ai_inference_total_requests gauge",
        "ai_inference_total_requests 1",
        "# HELP ai_inference_status_requests Number of inference requests by status code",
        "# TYPE ai_inference_status_requests gauge",
        'ai_inference_status_requests{status="200"} 1',
        "# HELP ai_inference_model_requests Number of inference requests by model",
        "# TYPE ai_inference_model_requests gauge",
        'ai_inference_model_requests{model="qwen"} 1',
        "ai_inference_latency_ms_count 1",
    ]

    for line in required_lines:
        assert line in body
