import pytest
from fastapi import HTTPException

from projects.ai_metrics_api import model_client


def test_call_model_server_rejects_unsupported_backend(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "unsupported")

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "unsupported model backend: unsupported"


class FakeModelServerResponse:
    status_code = 200

    def json(self):
        return {
            "model": "qwen2.5-7b",
            "status": 200,
            "latency_ms": 123,
            "tokens_in": 10,
            "tokens_out": 5,
        }


class FakeHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        return FakeModelServerResponse()


def test_call_model_server_supports_remote_http_backend(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(
        model_client,
        "MODEL_SERVER_URL",
        "http://gpu-server:8001/generate",
    )
    monkeypatch.setattr(model_client.httpx, "Client", FakeHttpClient)

    result = model_client.call_model_server(
        {
            "model": "qwen2.5-7b",
            "tokens_in": 10,
            "tokens_out": 5,
        }
    )

    assert result["model"] == "qwen2.5-7b"
    assert result["status"] == 200
    assert result["latency_ms"] == 123



class FakeTimeoutHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        raise model_client.httpx.TimeoutException("timed out")


class FakeUnavailableHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        raise model_client.httpx.RequestError("connection refused")


class FakeServerErrorResponse:
    status_code = 500

    def json(self):
        return {"detail": "backend failed"}


class FakeServerErrorHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        return FakeServerErrorResponse()


class FakeInvalidJsonResponse:
    status_code = 200

    def json(self):
        raise ValueError("invalid json")


class FakeInvalidJsonHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        return FakeInvalidJsonResponse()


def test_call_model_server_reports_timeout(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(model_client.httpx, "Client", FakeTimeoutHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == "model server request timed out"


def test_call_model_server_reports_unavailable_backend(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(model_client.httpx, "Client", FakeUnavailableHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "model server is unavailable"


def test_call_model_server_reports_backend_error_status(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(model_client.httpx, "Client", FakeServerErrorHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "model server returned status 500"


def test_call_model_server_reports_invalid_json(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(model_client.httpx, "Client", FakeInvalidJsonHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "model server returned invalid JSON"
