from fastapi import FastAPI
from typing import Optional

from projects.log_analyzer.analyze_logs import analyze_logs, parse_log_line

app = FastAPI()

LOG_PATH = "data/day02/inference.log"


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


@app.get("/metrics/logs")
def get_log_metrics():
    return analyze_logs(LOG_PATH)


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