import pytest
from fastapi import HTTPException

from projects.ai_metrics_api import backend_clients, model_client


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
    monkeypatch.setattr(backend_clients.httpx, "Client", FakeHttpClient)

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


class FakeVLLMResponse:
    status_code = 200

    def json(self):
        return {
            "model": "Qwen/Qwen2.5-1.5B-Instruct",
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 7,
            },
        }


class FakeVLLMHttpClient:
    request_url = None
    request_json = None

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        FakeVLLMHttpClient.request_url = url
        FakeVLLMHttpClient.request_json = json
        return FakeVLLMResponse()


def test_call_model_server_supports_vllm_backend(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "vllm")
    monkeypatch.setattr(model_client, "VLLM_BASE_URL", "http://vllm-server:8001/v1/")
    monkeypatch.setattr(model_client, "VLLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    monkeypatch.setattr(backend_clients.httpx, "Client", FakeVLLMHttpClient)

    result = model_client.call_model_server(
        {
            "prompt": "Say hello in one sentence.",
            "tokens_in": 10,
            "tokens_out": 32,
            "temperature": 0,
        }
    )

    assert FakeVLLMHttpClient.request_url == "http://vllm-server:8001/v1/chat/completions"
    assert FakeVLLMHttpClient.request_json["model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert FakeVLLMHttpClient.request_json["max_tokens"] == 32
    assert FakeVLLMHttpClient.request_json["temperature"] == 0
    assert result["model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert result["status"] == 200
    assert result["latency_ms"] >= 1
    assert result["tokens_in"] == 12
    assert result["tokens_out"] == 7


class FakeTimeoutHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        raise backend_clients.httpx.TimeoutException("timed out")


class FakeUnavailableHttpClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def post(self, url, json):
        raise backend_clients.httpx.RequestError("connection refused")


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
    monkeypatch.setattr(backend_clients.httpx, "Client", FakeTimeoutHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == "model server request timed out"


def test_call_model_server_reports_unavailable_backend(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(backend_clients.httpx, "Client", FakeUnavailableHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "model server is unavailable"


def test_call_model_server_reports_backend_error_status(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(backend_clients.httpx, "Client", FakeServerErrorHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "model server returned status 500"


def test_call_model_server_reports_invalid_json(monkeypatch):
    monkeypatch.setattr(model_client, "MODEL_BACKEND", "remote_http")
    monkeypatch.setattr(backend_clients.httpx, "Client", FakeInvalidJsonHttpClient)

    with pytest.raises(HTTPException) as exc_info:
        model_client.call_model_server({})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "model server returned invalid JSON"
