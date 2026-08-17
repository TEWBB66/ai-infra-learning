from fastapi import HTTPException

from projects.ai_metrics_api.backend_clients import MockBackendClient, VLLMBackendClient
from projects.ai_metrics_api.config import (
    MOCK_MODEL_SERVER_URL,
    MODEL_BACKEND,
    MODEL_SERVER_TIMEOUT_SEC,
    MODEL_SERVER_TIMEOUT_SECONDS,
    MODEL_SERVER_URL,
    VLLM_BASE_URL,
    VLLM_MODEL,
)


def get_backend_client():
    if MODEL_BACKEND in {"mock", "remote_http"}:
        return MockBackendClient(
            server_url=MODEL_SERVER_URL or MOCK_MODEL_SERVER_URL,
            timeout_seconds=MODEL_SERVER_TIMEOUT_SECONDS,
        )

    if MODEL_BACKEND == "vllm":
        return VLLMBackendClient(
            base_url=VLLM_BASE_URL,
            model=VLLM_MODEL,
            timeout_seconds=MODEL_SERVER_TIMEOUT_SEC,
        )

    raise HTTPException(
        status_code=500,
        detail=f"unsupported model backend: {MODEL_BACKEND}",
    )


def call_model_server(payload: dict) -> dict:
    return get_backend_client().infer(payload)
