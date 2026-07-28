from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
import random
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from projects.log_analyzer.analyze_logs import analyze_logs, parse_log_line

from projects.ai_metrics_api.config import (
    ALLOWED_FORCE_STATUS_CODES,
    DEFAULT_SLOW_THRESHOLD_MS,
    LOG_PATH,
    MODEL_ERROR_RATE_CRITICAL_THRESHOLD,
    MODEL_ERROR_RATE_WARNING_THRESHOLD,
    MODEL_P95_LATENCY_CRITICAL_MS,
    MODEL_P95_LATENCY_WARNING_MS,
    SERVICE_ERROR_RATE_CRITICAL_THRESHOLD,
    SERVICE_ERROR_RATE_WARNING_THRESHOLD,
    SERVICE_P95_LATENCY_CRITICAL_MS,
    SERVICE_P95_LATENCY_WARNING_MS,
    SERVICE_SLOW_REQUEST_CRITICAL_COUNT,
    SERVICE_SLOW_REQUEST_WARNING_COUNT,
)

app = FastAPI()

def add_alert(alerts, level, scope, metric, message, actual, threshold):
    alerts.append({
        "level": level,
        "scope": scope,
        "metric": metric,
        "message": message,
        "actual": actual,
        "threshold": threshold,
    })


def build_alerts(metrics):
    alerts = []

    error_rate = metrics["error_rate"]
    p95_latency_ms = metrics["p95_latency_ms"]
    slow_request_count = metrics["slow_request_count"]

    if error_rate >= SERVICE_ERROR_RATE_CRITICAL_THRESHOLD:
        add_alert(alerts,"critical","service","error_rate","service error rate is too high",error_rate,SERVICE_ERROR_RATE_CRITICAL_THRESHOLD)
    elif error_rate >= SERVICE_ERROR_RATE_WARNING_THRESHOLD:
        add_alert(alerts,"warning","service","error_rate","service error rate is elevated", error_rate,SERVICE_ERROR_RATE_WARNING_THRESHOLD)

    if p95_latency_ms >= SERVICE_P95_LATENCY_CRITICAL_MS:
        add_alert(alerts, "critical", "service", "p95_latency_ms", "service P95 latency is too high", p95_latency_ms, SERVICE_P95_LATENCY_CRITICAL_MS)
    elif p95_latency_ms >= SERVICE_P95_LATENCY_WARNING_MS:
        add_alert(alerts, "warning", "service", "p95_latency_ms", "service P95 latency is elevated", p95_latency_ms, SERVICE_P95_LATENCY_WARNING_MS)

    if slow_request_count >= SERVICE_SLOW_REQUEST_CRITICAL_COUNT:
        add_alert(alerts, "critical", "service", "slow_request_count", "too many slow requests", slow_request_count, SERVICE_SLOW_REQUEST_CRITICAL_COUNT)
    elif slow_request_count >= SERVICE_SLOW_REQUEST_WARNING_COUNT:
        add_alert(alerts, "warning", "service", "slow_request_count", "slow requests are increasing", slow_request_count, SERVICE_SLOW_REQUEST_WARNING_COUNT)

    for model_name, model_metrics in metrics["metrics_by_model"].items():
        model_error_rate = model_metrics["error_rate"]
        model_p95_latency_ms = model_metrics["p95_latency_ms"]

        if model_error_rate >= MODEL_ERROR_RATE_CRITICAL_THRESHOLD:
            add_alert(alerts, "critical", model_name, "error_rate", "model error rate is too high", model_error_rate, MODEL_ERROR_RATE_CRITICAL_THRESHOLD)
        elif model_error_rate >= MODEL_ERROR_RATE_WARNING_THRESHOLD:
            add_alert(alerts, "warning", model_name, "error_rate", "model error rate is elevated", model_error_rate, MODEL_ERROR_RATE_WARNING_THRESHOLD)

        if model_p95_latency_ms >= MODEL_P95_LATENCY_CRITICAL_MS:
            add_alert(alerts, "critical", model_name, "p95_latency_ms", "model P95 latency is too high", model_p95_latency_ms, MODEL_P95_LATENCY_CRITICAL_MS)
        elif model_p95_latency_ms >= MODEL_P95_LATENCY_WARNING_MS:
            add_alert(alerts, "warning", model_name, "p95_latency_ms", "model P95 latency is elevated", model_p95_latency_ms, MODEL_P95_LATENCY_WARNING_MS)

    service_status = "healthy"
    if any(alert["level"] == "critical" for alert in alerts):
        service_status = "critical"
    elif alerts:
        service_status = "warning"

    return {
        "service_status": service_status,
        "alert_count": len(alerts),
        "alerts": alerts,
    }

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
    allowed_status_codes = ALLOWED_FORCE_STATUS_CODES
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
def get_slow_requests(threshold_ms: int = DEFAULT_SLOW_THRESHOLD_MS):
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

@app.get("/metrics/alerts")
def get_alerts():
    metrics = analyze_logs(LOG_PATH)
    return build_alerts(metrics)