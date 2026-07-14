# AI Metrics API

This project provides a FastAPI service for analyzing simulated AI inference logs.

## Endpoints

- `GET /health`: health check
- `GET /metrics/logs`: summary metrics for inference logs
- `GET /metrics/slow`: slow request analysis
- `GET /metrics/slow?threshold_ms=300`: slow request analysis with custom threshold
- `GET /metrics/errors`: all error requests
- `GET /metrics/errors?status_code=500`: error requests filtered by status code

## Run

```bash
python -m uvicorn projects.ai_metrics_api.main:app --host 0.0.0.0 --port 8000