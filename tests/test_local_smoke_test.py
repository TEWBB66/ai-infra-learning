import json
from io import BytesIO
from urllib.error import HTTPError

from scripts import local_smoke_test


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def fake_urlopen(request, timeout):
    path = request.full_url.removeprefix("http://127.0.0.1:8000")

    if path == "/health":
        return FakeResponse(200, json.dumps({"status": "ok", "service": "ai-metrics-api"}))

    if path == "/ready":
        return FakeResponse(
            200,
            json.dumps({"status": "ready", "service": "ai-metrics-api", "backend": "mock"}),
        )

    if path == "/v1/infer":
        assert request.headers["X-client-id"] == "local-smoke-test"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["force_status"] == 200
        return FakeResponse(
            200,
            json.dumps(
                {
                    "request_id": "req-smoke",
                    "model": "qwen2.5-7b",
                    "status": 200,
                    "latency_ms": 10,
                    "tokens_in": 32,
                    "tokens_out": 8,
                }
            ),
        )

    if path == "/metrics/logs":
        return FakeResponse(
            200,
            json.dumps(
                {
                    "total_requests": 1,
                    "error_rate": 0,
                    "p95_latency_ms": 10,
                    "metrics_by_model": {},
                }
            ),
        )

    if path == "/metrics/prometheus":
        return FakeResponse(
            200,
            "\n".join(
                [
                    "ai_inference_total_requests 1",
                    "ai_inference_status_requests{status=\"200\"} 1",
                    "ai_inference_current_in_flight_requests 0",
                    "ai_inference_queue_depth 0",
                    "ai_inference_rate_limit_enabled 0",
                ]
            ),
        )

    raise AssertionError(f"unexpected URL: {request.full_url}")


def test_local_smoke_test_passes_with_expected_api_shape(monkeypatch, capsys):
    monkeypatch.setattr(local_smoke_test.urllib.request, "urlopen", fake_urlopen)

    exit_code = local_smoke_test.main([])

    assert exit_code == 0
    assert "Local smoke test passed" in capsys.readouterr().out


def test_local_smoke_test_returns_nonzero_on_http_error(monkeypatch):
    def raise_http_error(request, timeout):
        raise HTTPError(request.full_url, 503, "unavailable", headers={}, fp=BytesIO())

    monkeypatch.setattr(local_smoke_test.urllib.request, "urlopen", raise_http_error)

    assert local_smoke_test.main([]) == 1
