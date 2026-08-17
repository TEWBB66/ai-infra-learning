import time
from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException


class InferenceBackendClient(ABC):
    @abstractmethod
    def infer(self, payload: dict) -> dict:
        raise NotImplementedError


class MockBackendClient(InferenceBackendClient):
    def __init__(self, server_url: str, timeout_seconds: float):
        self.server_url = server_url
        self.timeout_seconds = timeout_seconds

    def infer(self, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.server_url, json=payload)
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


class VLLMBackendClient(InferenceBackendClient):
    def __init__(self, base_url: str, model: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def infer(self, payload: dict) -> dict:
        start_time = time.perf_counter()
        response_payload = self._post_chat_completion(payload)
        usage = response_payload.get("usage", {})

        return {
            "model": response_payload.get("model", self.model),
            "status": 200,
            "latency_ms": max(1, int((time.perf_counter() - start_time) * 1000)),
            "tokens_in": int(usage.get("prompt_tokens", payload.get("tokens_in", 0)) or 0),
            "tokens_out": int(usage.get("completion_tokens", payload.get("tokens_out", 0)) or 0),
        }

    def _post_chat_completion(self, payload: dict) -> dict:
        request_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": self._prompt_from_payload(payload),
                }
            ],
            "max_tokens": int(payload.get("max_tokens") or payload.get("tokens_out") or 80),
            "temperature": float(payload.get("temperature", 0)),
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    json=request_payload,
                )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="vLLM backend request timed out",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail="vLLM backend is unavailable",
            ) from exc

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"vLLM backend returned status {response.status_code}",
            )

        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="vLLM backend returned invalid JSON",
            ) from exc

    def _prompt_from_payload(self, payload: dict) -> str:
        if payload.get("prompt"):
            return payload["prompt"]

        return (
            "Answer concisely. This request is part of an LLM serving reliability benchmark. "
            f"Input token estimate: {payload.get('tokens_in', 0)}."
        )
