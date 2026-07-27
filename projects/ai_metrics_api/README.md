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
- per-model error rate
- model-level filtering
- 404 response for unknown model names
- mock inference endpoint that generates request logs
- request validation for token counts and forced status codes
- service-level and model-level alerting
- warning and critical alert levels
- automated tests for API endpoints and log analysis

## Endpoints

- `GET /health`: health check
- `GET /metrics/logs`: summary metrics, latency percentiles, and per-model metrics
- `GET /metrics/slow`: slow request analysis
- `GET /metrics/slow?threshold_ms=300`: slow request analysis with custom threshold
- `GET /metrics/errors`: all error requests
- `GET /metrics/errors?status_code=500`: error requests filtered by status code
- `GET /metrics/models`: per-model metrics
- `GET /metrics/models?model_name=qwen2.5-7b`: metrics for a specific model
- `POST /v1/mock-infer`: simulate an inference request and append one log line
- `GET /metrics/alerts`: service and model alert status

## Run

```bash
python -m uvicorn projects.ai_metrics_api.main:app --host 0.0.0.0 --port 8000
```

## Manual API Test

```bash
curl -s http://127.0.0.1:8000/health | jq
curl -s http://127.0.0.1:8000/metrics/logs | jq
curl -s http://127.0.0.1:8000/metrics/models | jq
curl -s "http://127.0.0.1:8000/metrics/models?model_name=qwen2.5-7b" | jq
curl -i "http://127.0.0.1:8000/metrics/models?model_name=unknown-model"

curl -s -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":300,"tokens_out":80}' | jq

curl -i -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":-1,"tokens_out":0}'

curl -i -X POST http://127.0.0.1:8000/v1/mock-infer \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-7b","tokens_in":10,"tokens_out":0,"force_status":999}'

curl -s http://127.0.0.1:8000/metrics/alerts | jq
```

## Automated Test

```bash
python -m pytest -q
```

Current test coverage includes:

- log analyzer summary metrics
- health check endpoint
- log metrics endpoint
- model metrics endpoint
- model filtering
- alerting endpoint
- mock inference success path
- mock inference validation errors

## API Docs

After starting the service, open:

```text
/docs
```