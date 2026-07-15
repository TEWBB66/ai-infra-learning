# AI Metrics API

This project provides a FastAPI service for analyzing simulated AI inference logs.

## Features

- health check
- summary metrics for inference logs
- average latency
- P95 and P99 latency
- slow request analysis with custom threshold
- error request filtering by status code
- per-model request count, error count, average latency, and P95 latency
- Swagger UI API documentation

## Endpoints

- `GET /health`: health check
- `GET /metrics/logs`: summary metrics, latency percentiles, and per-model metrics
- `GET /metrics/slow`: slow request analysis
- `GET /metrics/slow?threshold_ms=300`: slow request analysis with custom threshold
- `GET /metrics/errors`: all error requests
- `GET /metrics/errors?status_code=500`: error requests filtered by status code

## Run

```bash
python -m uvicorn projects.ai_metrics_api.main:app --host 0.0.0.0 --port 8000