from random import random
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Mock Model Server")

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


def estimate_latency_ms(model: str, tokens_in: int, tokens_out: int) -> int:
    total_tokens = tokens_in + tokens_out

    if model == "qwen2.5-14b":
        return 160 + int(total_tokens * 0.35)

    if model == "qwen2.5-7b":
        return 80 + int(total_tokens * 0.28)

    if model == "bge-reranker":
        return 40 + int(tokens_in * 0.12)

    return 100 + int(total_tokens * 0.3)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "mock-model-server"}


@app.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest):
    if request.force_status is not None:
        if request.force_status not in ALLOWED_STATUS_CODES:
            raise HTTPException(
                status_code=400,
                detail="force_status must be one of 200, 400, 429, 500",
            )
        status = request.force_status
    else:
        status = 500 if random() < 0.1 else 200

    latency_ms = estimate_latency_ms(
        request.model,
        request.tokens_in,
        request.tokens_out,
    )

    return {
        "model": request.model,
        "status": status,
        "latency_ms": latency_ms,
        "tokens_in": request.tokens_in,
        "tokens_out": request.tokens_out,
    }