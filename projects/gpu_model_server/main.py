import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="GPU Model Server")

ALLOWED_STATUS_CODES = {200, 400, 429, 500}


class GenerateRequest(BaseModel):
    model: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    force_status: Optional[int] = None


class GenerateResponse(BaseModel):
    model: str
    status: int
    latency_ms: int
    tokens_in: int
    tokens_out: int


def estimate_gpu_latency_ms(model: str, tokens_in: int, tokens_out: int) -> int:
    total_tokens = tokens_in + tokens_out

    if model == "qwen2.5-1.5b":
        return 70 + int(total_tokens * 0.18)

    if model == "qwen2.5-0.5b":
        return 45 + int(total_tokens * 0.12)

    return 90 + int(total_tokens * 0.2)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gpu-model-server",
    }


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest):
    if request.force_status is not None and request.force_status not in ALLOWED_STATUS_CODES:
        raise HTTPException(
            status_code=400,
            detail="force_status must be one of 200, 400, 429, 500",
        )

    start_time = time.perf_counter()

    status = request.force_status or 200
    estimated_latency_ms = estimate_gpu_latency_ms(
        request.model,
        request.tokens_in,
        request.tokens_out,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    latency_ms = max(estimated_latency_ms, elapsed_ms)

    return {
        "model": request.model,
        "status": status,
        "latency_ms": latency_ms,
        "tokens_in": request.tokens_in,
        "tokens_out": request.tokens_out,
    }