from fastapi import HTTPException
from fastapi.testclient import TestClient

from projects.ai_metrics_api import main
from projects.ai_metrics_api.rate_limiter import FixedWindowRateLimiter


client = TestClient(main.app)


def fake_success(payload):
    return {
        "model": payload["model"],
        "status": 200,
        "latency_ms": 12,
        "tokens_in": payload["tokens_in"],
        "tokens_out": payload["tokens_out"],
    }


def assert_error_contract(body, error_code, message):
    assert body["detail"] == message
    assert body["message"] == message
    assert body["error_code"] == error_code
    assert body["request_id"].startswith("req-") or body["request_id"] == "req-error-contract"
    assert body["trace_id"].startswith("trace-") or body["trace_id"] == "trace-error-contract"


def test_auth_error_response_has_stable_contract(monkeypatch):
    monkeypatch.setattr(main, "REQUIRE_API_KEY", True)
    monkeypatch.setattr(main, "API_KEY", "test-key")

    response = client.post(
        "/v1/infer",
        headers={
            "X-Request-ID": "req-error-contract",
            "X-Trace-ID": "trace-error-contract",
        },
        json={"model": "qwen", "tokens_in": 1, "tokens_out": 2},
    )

    assert response.status_code == 401
    body = response.json()
    assert_error_contract(body, "auth_missing", "missing API key")
    assert body["request_id"] == "req-error-contract"
    assert body["trace_id"] == "trace-error-contract"


def test_rate_limit_error_response_keeps_request_context(monkeypatch, tmp_path):
    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "RATE_LIMITER", FixedWindowRateLimiter(True, 0, 60))
    monkeypatch.setattr(main, "call_model_server", fake_success)

    response = client.post(
        "/v1/infer",
        headers={
            "X-Request-ID": "req-error-contract",
            "X-Trace-ID": "trace-error-contract",
            "X-Client-ID": "client-a",
        },
        json={"model": "qwen", "tokens_in": 8, "tokens_out": 16},
    )

    assert response.status_code == 429
    body = response.json()
    assert_error_contract(body, "rate_limit_exceeded", "rate limit exceeded")
    assert body["request_id"] == "req-error-contract"
    assert body["trace_id"] == "trace-error-contract"

    log_text = temp_log_path.read_text(encoding="utf-8")
    assert "request_id=req-error-contract" in log_text
    assert "trace_id=trace-error-contract" in log_text
    assert "client_id=client-a" in log_text
    assert "status=429" in log_text


def test_backend_error_response_keeps_request_context(monkeypatch, tmp_path):
    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))

    def fail_backend(payload):
        raise HTTPException(status_code=502, detail="model backend unavailable")

    monkeypatch.setattr(main, "call_model_server", fail_backend)

    response = client.post(
        "/v1/infer",
        headers={
            "X-Request-ID": "req-error-contract",
            "X-Trace-ID": "trace-error-contract",
            "X-Client-ID": "client-a",
        },
        json={"model": "qwen", "tokens_in": 8, "tokens_out": 16},
    )

    assert response.status_code == 502
    body = response.json()
    assert_error_contract(body, "backend_unavailable", "model backend unavailable")
    assert body["request_id"] == "req-error-contract"
    assert body["trace_id"] == "trace-error-contract"

    log_text = temp_log_path.read_text(encoding="utf-8")
    assert "request_id=req-error-contract" in log_text
    assert "trace_id=trace-error-contract" in log_text
    assert "client_id=client-a" in log_text
    assert "status=502" in log_text
