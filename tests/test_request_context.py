from fastapi.testclient import TestClient

from projects.ai_metrics_api.main import app


client = TestClient(app)


def fake_call_model_server(payload):
    return {
        "model": payload["model"],
        "status": 200,
        "latency_ms": 25,
        "tokens_in": payload["tokens_in"],
        "tokens_out": payload["tokens_out"],
    }


def test_infer_accepts_request_and_trace_headers(monkeypatch, tmp_path):
    from projects.ai_metrics_api import main

    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    response = client.post(
        "/v1/infer",
        headers={
            "X-Request-ID": "req-client-123",
            "X-Trace-ID": "trace-client-456",
        },
        json={
            "model": "qwen",
            "tokens_in": 8,
            "tokens_out": 16,
        },
    )

    assert response.status_code == 200
    assert response.json()["request_id"] == "req-client-123"
    assert response.json()["trace_id"] == "trace-client-456"

    log_text = temp_log_path.read_text(encoding="utf-8")
    assert "request_id=req-client-123" in log_text
    assert "trace_id=trace-client-456" in log_text


def test_infer_generates_trace_id_when_header_is_absent(monkeypatch, tmp_path):
    from projects.ai_metrics_api import main

    temp_log_path = tmp_path / "inference.log"
    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "call_model_server", fake_call_model_server)

    response = client.post(
        "/v1/infer",
        json={
            "model": "qwen",
            "tokens_in": 8,
            "tokens_out": 16,
        },
    )

    assert response.status_code == 200
    assert response.json()["request_id"].startswith("req-")
    assert response.json()["trace_id"].startswith("trace-")
    assert "trace_id=trace-" in temp_log_path.read_text(encoding="utf-8")


def test_infer_rejects_invalid_trace_header():
    response = client.post(
        "/v1/infer",
        headers={"X-Trace-ID": "bad trace id"},
        json={
            "model": "qwen",
            "tokens_in": 8,
            "tokens_out": 16,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid X-Trace-ID"


def test_mock_infer_preserves_trace_on_backend_failure(monkeypatch, tmp_path):
    from fastapi import HTTPException
    from projects.ai_metrics_api import main

    temp_log_path = tmp_path / "inference.log"

    def failing_call_model_server(payload):
        raise HTTPException(status_code=502, detail="model server is unavailable")

    monkeypatch.setattr(main, "LOG_BACKEND", "file")
    monkeypatch.setattr(main, "LOG_PATH", str(temp_log_path))
    monkeypatch.setattr(main, "call_model_server", failing_call_model_server)

    response = client.post(
        "/v1/mock-infer",
        headers={
            "X-Request-ID": "req-failure-1",
            "X-Trace-ID": "trace-failure-1",
        },
        json={
            "model": "qwen",
            "tokens_in": 8,
            "tokens_out": 16,
        },
    )

    assert response.status_code == 502
    log_text = temp_log_path.read_text(encoding="utf-8")
    assert "request_id=req-failure-1" in log_text
    assert "trace_id=trace-failure-1" in log_text
    assert "status=502" in log_text
