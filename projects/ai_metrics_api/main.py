from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
import random
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from projects.log_analyzer.analyze_logs import analyze_logs, parse_log_line

app = FastAPI()

LOG_PATH = "data/day02/inference.log"

class MockInferRequest(BaseModel):
    model: str = "qwen2.5-7b"
    endpoint: str = "/v1/mock-infer"
    tokens_in: int = Field(default=256, ge=0)
    tokens_out: int = Field(default=80, ge=0)
    force_status: Optional[int] = None


def estimate_latency_ms(model: str, tokens_in: int, tokens_out: int) -> int:
    base_latency_by_model = {
        "qwen2.5-7b": 120,
        "qwen2.5-14b": 260,
        "bge-reranker": 60,
    }

    base_latency = base_latency_by_model.get(model, 180)
    token_latency = int(tokens_in * 0.08 + tokens_out * 0.6)
    jitter = random.randint(0, 80)

    return base_latency + token_latency + jitter


def build_log_line(
    request_id: str,
    model: str,
    endpoint: str,
    status: int,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return (
        f"{timestamp} "
        f"request_id={request_id} "
        f"model={model} "
        f"endpoint={endpoint} "
        f"status={status} "
        f"latency_ms={latency_ms} "
        f"tokens_in={tokens_in} "
        f"tokens_out={tokens_out}"
    )


def append_log_line(line: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def load_records():
    records = []

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            record = parse_log_line(line)
            records.append(record)

    return records


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ai-metrics-api",
    }

@app.post("/v1/mock-infer")
def mock_infer(request: MockInferRequest):
    allowed_status_codes = {200, 400, 429, 500}
    if request.force_status is not None and request.force_status not in allowed_status_codes:
        raise HTTPException(
            status_code=400,
            detail="force_status must be one of 200, 400, 429, 500",
        )
    request_id = f"req-{uuid4().hex[:8]}"
    latency_ms = estimate_latency_ms(
        request.model,
        request.tokens_in,
        request.tokens_out,
    )

    if request.force_status is not None:
        status = request.force_status
    else:
        status = 200

    time.sleep(latency_ms / 1000)

    log_line = build_log_line(
        request_id=request_id,
        model=request.model,
        endpoint=request.endpoint,
        status=status,
        latency_ms=latency_ms,
        tokens_in=request.tokens_in,
        tokens_out=request.tokens_out,
    )
    append_log_line(log_line)

    return {
        "request_id": request_id,
        "model": request.model,
        "status": status,
        "latency_ms": latency_ms,
        "tokens_in": request.tokens_in,
        "tokens_out": request.tokens_out,
    }

@app.get("/metrics/logs")
def get_log_metrics():
    return analyze_logs(LOG_PATH)

@app.get("/metrics/models")
def get_model_metrics(model_name: Optional[str] = None):
    metrics = analyze_logs(LOG_PATH)
    metrics_by_model = metrics["metrics_by_model"]
    if model_name is None:
        return {
            "metrics_by_model": metrics_by_model,
        }
        
    if model_name not in metrics_by_model:
        raise HTTPException(status_code=404, detail="model not found")

    return {
    "model_name": model_name,
    "metrics": metrics_by_model[model_name],
}

@app.get("/metrics/slow")
def get_slow_requests(threshold_ms: int = 200):
    records = load_records()

    slow_records = []
    for record in records:
        latency = int(record["latency_ms"])
        if latency > threshold_ms:
            slow_records.append({
                "request_id": record["request_id"],
                "model": record["model"],
                "status": int(record["status"]),
                "latency_ms": latency,
            })

    return {
        "threshold_ms": threshold_ms,
        "slow_request_count": len(slow_records),
        "slow_requests": slow_records,
    }


@app.get("/metrics/errors")
def get_error_requests(status_code: Optional[int] = None):
    records = load_records()

    error_records = []
    for record in records:
        status = int(record["status"])

        if status_code is not None:
            is_error = status == status_code
        else:
            is_error = status >= 400

        if is_error:
            error_records.append({
                "request_id": record["request_id"],
                "model": record["model"],
                "status": status,
                "latency_ms": int(record["latency_ms"]),
            })

    return {
        "status_code": status_code,
        "error_request_count": len(error_records),
        "error_requests": error_records,
    }