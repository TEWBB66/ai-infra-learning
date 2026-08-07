import httpx

from fastapi import HTTPException

from projects.ai_metrics_api.config import (
    MODEL_BACKEND,
    MODEL_SERVER_TIMEOUT_SECONDS,
    MODEL_SERVER_URL,
)


def call_model_server(payload: dict) -> dict:
    if MODEL_BACKEND not in {"mock", "remote_http"}:
        raise HTTPException(
            status_code=500,
            detail=f"unsupported model backend: {MODEL_BACKEND}",
        )

    try:
        with httpx.Client(timeout=MODEL_SERVER_TIMEOUT_SECONDS) as client:
            response = client.post(MODEL_SERVER_URL, json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="model server request timed out",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="model server is unavailable",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"model server returned status {response.status_code}",
        )

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="model server returned invalid JSON",
        ) from exc