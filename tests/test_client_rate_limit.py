from fastapi.testclient import TestClient

from projects.ai_metrics_api.main import app
from projects.ai_metrics_api.rate_limiter import FixedWindowRateLimiter


client = TestClient(app)


def fake_call_model_server(payload):
    return {
        "model": payload["model"],
        "status": 200,
        "latency_ms": 10,
        "tokens_in": payload["tokens_in"],
        "tokens_out": payload["tokens_out"],
    }


def test_rate_limit_rejects_same_client_after_limit(monkeypatch, tmp_path):
    from projects.ai_metrics_api import main

    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "RATE_LIMITER", FixedWindowRateLimiter(True, 1, 60))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    payload = {"model": "qwen", "tokens_in": 8, "tokens_out": 16}
    headers = {"X-Client-ID": "client-a", "X-Trace-ID": "trace-a"}

    first = client.post("/v1/infer", headers=headers, json=payload)
    second = client.post("/v1/infer", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "rate limit exceeded"

    log_text = temp_log_path.read_text(encoding="utf-8")
    assert "client_id=client-a" in log_text
    assert "trace_id=trace-a" in log_text
    assert "status=429" in log_text


def test_rate_limit_tracks_clients_independently(monkeypatch, tmp_path):
    from projects.ai_metrics_api import main

    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "RATE_LIMITER", FixedWindowRateLimiter(True, 1, 60))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    payload = {"model": "qwen", "tokens_in": 8, "tokens_out": 16}

    first = client.post("/v1/infer", headers={"X-Client-ID": "client-a"}, json=payload)
    second = client.post("/v1/infer", headers={"X-Client-ID": "client-b"}, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200


def test_rate_limit_rejects_invalid_client_header():
    response = client.post(
        "/v1/infer",
        headers={"X-Client-ID": "bad client"},
        json={"model": "qwen", "tokens_in": 8, "tokens_out": 16},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid X-Client-ID"


def test_prometheus_exports_rate_limit_metrics(monkeypatch):
    from projects.ai_metrics_api import main

    limiter = FixedWindowRateLimiter(True, 1, 60)
    limiter.allow("client-a", now=1.0)
    limiter.allow("client-a", now=2.0)
    monkeypatch.setattr(main, "RATE_LIMITER", limiter)

    response = client.get("/metrics/prometheus")

    assert response.status_code == 200
    body = response.text
    assert "ai_inference_rate_limit_enabled 1" in body
    assert "ai_inference_rate_limit_active_clients 1" in body
    assert "ai_inference_rate_limit_rejected_total 1" in body
